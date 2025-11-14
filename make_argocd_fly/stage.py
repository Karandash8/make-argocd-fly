import logging
import os
import shutil
import asyncio
import textwrap
import fnmatch
import yaml
import yaml.composer
import yaml.parser
import yaml.scanner
import yaml.constructor
from pathlib import PurePosixPath
from typing import Any
from pprint import pformat
from typing import Protocol, Iterable

try:
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  from yaml import SafeLoader

from make_argocd_fly.context import Context, ctx_get, ctx_set, resolve_expr
from make_argocd_fly.context.data import Content, Template, OutputResource
from make_argocd_fly.resource.viewer import ScopedViewer, ResourceType
from make_argocd_fly import default
from make_argocd_fly.resource.writer import (AsyncWriterProto, writer_factory,
                                             SyncToAsyncWriter, YamlWriter)
from make_argocd_fly.param import ParamNames
from make_argocd_fly.config import get_config
from make_argocd_fly.cliparam import get_cli_params
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.exception import (UndefinedTemplateVariableError, TemplateRenderingError, InternalError,
                                       KustomizeError, PathDoesNotExistError, ConfigFileError, HelmfileError,
                                       OutputFilenameConstructionError)
from make_argocd_fly.util import extract_single_resource, get_app_rel_path
from make_argocd_fly.limits import RuntimeLimits
from make_argocd_fly.namegen import (K8sInfo, SourceInfo, K8sPolicy, SourcePolicy, Deduper, RoutingRules,
                                     KUSTOMIZE_BASENAMES, HELMFILE_BASENAMES)
from make_argocd_fly.type import PipelineType


log = logging.getLogger(__name__)


class Stage(Protocol):
  name: str
  requires: dict[str, str]
  provides: dict[str, str]

  async def run(self, ctx: Context) -> None: ...


def _resolve_template_vars(env_name: str, app_name: str) -> dict:
  config = get_config()
  extra = {
    'argocd_application_cr_template': default.ARGOCD_APPLICATION_CR_TEMPLATE,
    '__application': {
      'application_name': '-'.join([os.path.basename(app_name), env_name]).replace('_', '-'),
      'path': os.path.join(os.path.basename(config.output_dir), env_name, app_name)
    },
    'argocd': default.ARGOCD_DEFAULTS,
    'env_name': env_name,
    'app_name': app_name,
  }
  vars_ = config.get_vars(env_name=env_name, app_name=app_name, extra_vars=extra)

  if get_cli_params().print_vars:
    log.info(f'Variables for application {app_name} in environment {env_name}:\n{pformat(vars_)}')

  return vars_


def _scan_viewer(viewer: ScopedViewer,
                 resource_types: list[ResourceType] | None,
                 template: bool,
                 search_subdirs: list[str] | None = None,
                 excludes: Iterable[str] | None = None):
  '''
  Scan resources from the viewer and filter them using optional exclude patterns.
  Exclude patterns are POSIX-like relative paths; they support both prefix and glob
  semantics via _is_match().
  '''
  out = []
  exclude_patterns = list(excludes or [])

  for child in viewer.search_subresources(resource_types=resource_types,
                                          template=template,
                                          search_subdirs=search_subdirs):
    if exclude_patterns and _is_match(child.rel_path, exclude_patterns):
      log.debug(f'Excluding {child.rel_path}')
      continue
    out.append(child)
  return out


def _ensure_list(value: Any, param_name: str) -> list[str]:
  if value is None:
    return []

  if not isinstance(value, list):
    log.error(f'Application parameter {param_name} must be a list')
    raise InternalError()

  return value


def _is_match(path: str, patterns: Iterable[str]) -> bool:
  '''Match by prefix or glob; patterns are posix-like relative paths.'''
  posix = str(PurePosixPath(path))
  for pat in patterns:
    pat_posix = str(PurePosixPath(pat))

    # prefix match
    if posix.startswith(pat_posix.rstrip('/')):
      return True

    # glob match
    if fnmatch.fnmatch(posix, pat_posix):
      return True

  return False


def _is_one_of(path: str, names: Iterable[str]) -> bool:
  '''True if basename (case-sensitive) is in names.'''
  return PurePosixPath(path).name in names


class DiscoverK8sSimpleApplication(Stage):
  name = 'DiscoverK8sSimpleApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    app_params = get_config().get_params(ctx.env_name, ctx.app_name)
    viewer = ctx_get(ctx, self.requires['viewer'])

    _ensure_list(app_params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)

    content = []
    for child in _scan_viewer(viewer,
                              resource_types=[ResourceType.YAML],
                              template=False,
                              excludes=app_params.exclude_rendering):
      content.append(Content(resource_type=child.resource_type, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['content'], content)

    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)
    templates = []
    for child in _scan_viewer(viewer,
                              resource_types=[ResourceType.YAML],
                              template=True,
                              excludes=app_params.exclude_rendering):
      templates.append(Template(resource_type=child.resource_type, vars=resolved_vars, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['template'], templates)

    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class DiscoverK8sKustomizeApplication(Stage):
  name = 'DiscoverK8sKustomizeApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    app_params = get_config().get_params(ctx.env_name, ctx.app_name)
    viewer = ctx_get(ctx, self.requires['viewer'])

    _ensure_list(app_params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)

    # TODO: this will not work if there is a directory named `base` in addition to the kustomize base
    search_subdirs = ['base', ctx.env_name] if list(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY],
                                                                               name_pattern='base$')) else None

    content = []
    for child in _scan_viewer(viewer,
                              resource_types=[ResourceType.YAML],
                              template=False,
                              search_subdirs=search_subdirs,
                              excludes=app_params.exclude_rendering):
      content.append(Content(resource_type=child.resource_type, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['content'], content)

    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)
    templates = []
    for child in _scan_viewer(viewer,
                              resource_types=[ResourceType.YAML],
                              template=True,
                              search_subdirs=search_subdirs,
                              excludes=app_params.exclude_rendering):
      templates.append(Template(resource_type=child.resource_type, vars=resolved_vars, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['template'], templates)

    ctx_set(ctx, self.provides['tmp_dir'], config.tmp_dir)
    ctx_set(ctx, self.provides['output_dir'], config.output_dir)

    if list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                       name_pattern='kustomization|Kustomization',
                                       search_subdirs=[ctx.env_name],
                                       depth=1)):
      kustomize_exec_dir = ctx.env_name
    elif list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                         name_pattern='kustomization|Kustomization',
                                         search_subdirs=['base'],
                                         depth=1)):
      kustomize_exec_dir = 'base'
    elif list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                         name_pattern='kustomization|Kustomization',
                                         depth=1)):
      kustomize_exec_dir = '.'
    else:
      # TODO: this doesn't skip anything, just logs an error
      kustomize_exec_dir = ''
      log.error(f'Missing kustomization.yml in the application directory. Skipping application {ctx.app_name} in environment {ctx.env_name}')

    ctx_set(ctx, self.provides['kustomize_exec_dir'], kustomize_exec_dir)


class DiscoverK8sHelmfileApplication(Stage):
  name = 'DiscoverK8sHelmfileApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    app_params = get_config().get_params(ctx.env_name, ctx.app_name)
    viewer = ctx_get(ctx, self.requires['viewer'])

    _ensure_list(app_params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)

    content = []
    for child in _scan_viewer(viewer,
                              resource_types=[ResourceType.YAML],
                              template=False,
                              excludes=app_params.exclude_rendering):
      content.append(Content(resource_type=child.resource_type, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['content'], content)

    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)
    templates = []
    for child in _scan_viewer(viewer,
                              resource_types=[ResourceType.YAML],
                              template=True,
                              excludes=app_params.exclude_rendering):
      templates.append(Template(resource_type=child.resource_type, vars=resolved_vars, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['template'], templates)

    ctx_set(ctx, self.provides['tmp_dir'], config.tmp_dir)
    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class DiscoverK8sAppOfAppsApplication(Stage):
  name = 'DiscoverK8sAppOfAppsApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()

    discovered_apps = []
    for env_name in config.list_envs():
      for app_name in config.list_apps(env_name):
        app_params = config.get_params(env_name, app_name)

        if app_params.parent_app:
          if (app_params.parent_app == ctx.app_name and
              ((app_params.parent_app_env is None and env_name == ctx.env_name) or
                (app_params.parent_app_env is not None and app_params.parent_app_env == ctx.env_name))):
            discovered_apps.append((env_name, app_name))

    templates = []
    for env_name, app_name in discovered_apps:
      resolved_vars = _resolve_template_vars(env_name, app_name)

      try:
        templates.append(Template(
          resource_type=ResourceType.YAML,
          vars=resolved_vars,
          data=textwrap.dedent(resolved_vars['argocd_application_cr_template']),
          source='Application',
        ))
      except TypeError:
        log.error(f'Error rendering Jinja template for application {ctx.app_name} in environment {ctx.env_name}. '
                  f'Ensure that the template is correctly defined in the config file.')
        raise ConfigFileError

    ctx_set(ctx, self.provides['template'], templates)

    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class DiscoverGenericApplication(Stage):
  name = 'DiscoverGenericApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    app_params = get_config().get_params(ctx.env_name, ctx.app_name)
    viewer = ctx_get(ctx, self.requires['viewer'])

    _ensure_list(app_params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)

    file_types = [resource_type for resource_type in ResourceType if
                  (resource_type != ResourceType.DIRECTORY and
                   resource_type != ResourceType.DOES_NOT_EXIST)]

    content = []
    for child in _scan_viewer(viewer,
                              resource_types=file_types,
                              template=False,
                              excludes=app_params.exclude_rendering):
      content.append(Content(resource_type=child.resource_type, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['content'], content)

    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)
    templates = []
    for child in _scan_viewer(viewer,
                              resource_types=file_types,
                              template=True,
                              excludes=app_params.exclude_rendering):
      templates.append(Template(resource_type=child.resource_type, vars=resolved_vars, data=child.content, source=child.rel_path))
    ctx_set(ctx, self.provides['template'], templates)

    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class RenderTemplates(Stage):
  name = 'RenderTemplates'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    templates = ctx_get(ctx, self.requires['template'])
    viewer = ctx_get(ctx, self.requires['viewer'])

    renderer = JinjaRenderer()
    renderer.set_resource_viewer(viewer)
    content = []

    for template in templates:
      renderer.set_template_vars(template.vars)
      renderer.set_template_source(template.source)

      try:
        result = renderer.render(template.data)

        content.append(Content(
          resource_type=template.resource_type,
          data=result,
          source=template.source,
        ))

      except (UndefinedTemplateVariableError, PathDoesNotExistError):
        log.error(f'Error rendering template {template.source}')
        raise TemplateRenderingError(template.source, ctx.app_name, ctx.env_name) from None

    ctx_set(ctx, self.provides['content'], content)


class SplitManifests(Stage):
  name = 'SplitManifests'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    content = resolve_expr(ctx, self.requires['content'])

    split_content = []
    for item in content:
      if item.resource_type == ResourceType.YAML:
        for single in extract_single_resource(item.data):
          split_content.append(Content(
            resource_type=ResourceType.YAML,
            data=single,
            source=item.source,
          ))
      else:
        split_content.append(item)

    ctx_set(ctx, self.provides['content'], split_content)


class ConvertToYaml(Stage):
  name = 'ConvertToYaml'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    items = resolve_expr(ctx, self.requires['content'])
    out: list[Content] = []

    for it in items:
      if it.resource_type == ResourceType.YAML:
        try:
          obj = yaml.load(it.data, Loader=SafeLoader)
          out.append(Content(
            resource_type=it.resource_type,
            data=it.data,
            source=it.source,
            yaml_obj=obj
          ))
        except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError, yaml.constructor.ConstructorError):
          log.debug(f'YAML parse failed in ConvertToYaml for {it.source}; leaving as text')
          out.append(it)
      else:
        out.append(it)

    ctx_set(ctx, self.provides['content'], out)


class GenerateNames(Stage):
  name = 'GenerateNames'

  def __init__(self, requires: dict[str, str],
               provides: dict[str, str],
               *,
               pipeline_kind: PipelineType) -> None:
    self.requires = requires
    self.provides = provides
    self.pipeline_kind = pipeline_kind
    self.k8s_policy = K8sPolicy()
    self.src_policy = SourcePolicy()

    if self.pipeline_kind is None:
      log.error(f'PipelineType must be provided to {self.name} stage')
      raise InternalError()

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} (pipeline_kind={self.pipeline_kind})')
    items = resolve_expr(ctx, self.requires['content'])

    rules = RoutingRules(
      pipeline_kind=self.pipeline_kind,
      kustomize_cfg=set(resolve_expr(ctx, 'discover.kustomize.config_files') or []),
      helmfile_cfg=set(resolve_expr(ctx, 'discover.helmfile.config_files') or []),
    )

    app_rel = get_app_rel_path(ctx.env_name, ctx.app_name)
    dedupe = Deduper()
    out: list[OutputResource] = []

    for res in sorted(items, key=lambda r: r.source):
      log.debug(f'Processing resource: {res.source}')
      policy_key = self._route_policy(res, rules)

      src = SourceInfo.from_source_path(res.source)

      try:
        if policy_key == 'k8s':
          k8s = K8sInfo.from_yaml_obj(getattr(res, 'yaml_obj', None))
          rel = self.k8s_policy.render(k8s=k8s, src=src)
        elif policy_key == 'source':
          rel = self.src_policy.render(k8s=None, src=src)
        else:
          log.warning(f'Skipping resource due to unknown policy \'{policy_key}\': {res.source}')
          continue
      except OutputFilenameConstructionError as e:
        log.warning(f'Failed to construct output filename for {res.source} {e}')
        continue

      rel = dedupe.unique(rel)
      out.append(OutputResource(
        resource_type=res.resource_type,
        data=res.data,
        source=res.source,
        output_path=os.path.join(app_rel, rel),
        yaml_obj=getattr(res, 'yaml_obj', None),
      ))

    ctx_set(ctx, self.provides['files'], out)

  def _route_policy(self, res, rules: RoutingRules) -> str | None:
    # Generic pipeline: always name by source
    if rules.pipeline_kind == PipelineType.GENERIC:
      return 'source'

    # K8s pipelines
    if rules.pipeline_kind == PipelineType.K8S_KUSTOMIZE:
      # SourcePolicy for kustomization and values files
      if _is_one_of(res.source, KUSTOMIZE_BASENAMES) or res.source in rules.kustomize_cfg:
        return 'source'
      return 'k8s' if res.resource_type == ResourceType.YAML else None

    if rules.pipeline_kind == PipelineType.K8S_HELMFILE:
      # SourcePolicy for helmfile
      if _is_one_of(res.source, HELMFILE_BASENAMES) or res.source in rules.helmfile_cfg:
        return 'source'
      return 'k8s' if res.resource_type == ResourceType.YAML else None

    if rules.pipeline_kind in (PipelineType.K8S_SIMPLE, PipelineType.K8S_APP_OF_APPS):
      return 'k8s' if res.resource_type == ResourceType.YAML else None

    return None


class WriteOnDisk(Stage):
  name = 'WriteOnDisk'

  def __init__(self, requires: dict[str, str], provides: dict[str, str], *, limits: RuntimeLimits) -> None:
    self.requires = requires
    self.provides = provides
    self.limits = limits
    self._written = set()

    if self.limits is None:
      log.error(f'RuntimeLimits must be provided to {self.name} stage')
      raise InternalError()

  async def _write_one(self, writer: AsyncWriterProto, output_dir: str, ctx: Context, resource: OutputResource) -> None:
    async with self.limits.io_sem:
      path = os.path.join(output_dir, resource.output_path)
      if path in self._written:
        log.error(f'Duplicate output: {path}')
        raise InternalError()
      self._written.add(path)

      await writer.write_async(path,
                               resource.yaml_obj if getattr(resource, 'yaml_obj', None) is not None else resource.data,
                               ctx.env_name, ctx.app_name, resource.source)

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    files = ctx_get(ctx, self.requires['files'])
    output_dir = ctx_get(ctx, self.requires['output_dir'])
    self._written = set()

    app_output_dir = os.path.join(output_dir, get_app_rel_path(ctx.env_name, ctx.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    try:
      async with asyncio.TaskGroup() as tg:
        for res in sorted(files, key=lambda r: r.output_path):
          # pick writer: yaml_obj present , hence yaml writer; else generic
          if getattr(res, 'yaml_obj', None) is not None:
            # force YAML writer
            async_writer = SyncToAsyncWriter(YamlWriter())
          else:
            async_writer = SyncToAsyncWriter(writer_factory(
              get_config().get_params(ctx.env_name, ctx.app_name).app_type,
              res.resource_type
            ))
          tg.create_task(self._write_one(async_writer, output_dir, ctx, res))
    except ExceptionGroup as e:
      if e.exceptions:
        raise e.exceptions[0]
      else:
        raise e


class KustomizeBuild(Stage):
  name = 'KustomizeBuild'

  def __init__(self, requires: dict[str, str], provides: dict[str, str], *, limits: RuntimeLimits) -> None:
    self.requires = requires
    self.provides = provides
    self.limits = limits

    if self.limits is None:
      log.error(f'RuntimeLimits must be provided to {self.name} stage')
      raise InternalError()

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    kustomize_exec_dir = ctx_get(ctx, self.requires['kustomize_exec_dir'])
    tmp_dir = ctx_get(ctx, self.requires['tmp_dir'])

    dir_path = os.path.normpath(os.path.join(tmp_dir, get_app_rel_path(ctx.env_name, ctx.app_name), kustomize_exec_dir))
    retries = 3

    try:
      async with self.limits.subproc_sem:
        for attempt in range(retries):
          proc = await asyncio.create_subprocess_exec(
            'kustomize', 'build', '--enable-helm', '.',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=dir_path)

          stdout, stderr = await proc.communicate()
          if proc.returncode != 0:
            log.error(f'Kustomize error: {stderr.decode("utf-8", "ignore")}')

            delay = min(2 ** attempt, 4) + (attempt * 0.1)
            log.info(f'Retrying {attempt + 1}/{retries} after {delay:.1f}s')
            await asyncio.sleep(delay)
            continue
          break
        else:
          raise KustomizeError(ctx.app_name, ctx.env_name)
    except FileNotFoundError as e:
      log.error(f'Failed generating application {ctx.app_name} in environment {ctx.env_name}')
      raise e

    ymls = []

    ymls.append(Content(
        resource_type=ResourceType.YAML,
        data=stdout.decode('utf-8'),
        source='Kustomize'
    ))
    ctx_set(ctx, self.provides['content'], ymls)


class HelmfileRun(Stage):
  name = 'HelmfileRun'

  def __init__(self, requires: dict[str, str], provides: dict[str, str], *, limits: RuntimeLimits) -> None:
    self.requires = requires
    self.provides = provides
    self.limits = limits

    if self.limits is None:
      log.error(f'RuntimeLimits must be provided to {self.name} stage')
      raise InternalError()

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    tmp_dir = ctx_get(ctx, self.requires['tmp_dir'])

    dir_path = os.path.join(tmp_dir, get_app_rel_path(ctx.env_name, ctx.app_name))
    retries = 3

    try:
      async with self.limits.subproc_sem:
        for attempt in range(retries):
          proc = await asyncio.create_subprocess_exec(
            'helmfile', 'template', '--quiet',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=dir_path)

          stdout, stderr = await proc.communicate()
          if proc.returncode != 0:
            log.error(f'Helmfile error: {stderr.decode("utf-8", "ignore")}')

            delay = min(2 ** attempt, 4) + (attempt * 0.1)
            log.info(f'Retrying {attempt + 1}/{retries} after {delay:.1f}s')
            await asyncio.sleep(delay)
            continue
          break
        else:
          raise HelmfileError(ctx.app_name, ctx.env_name)
    except FileNotFoundError as e:
      log.error(f'Failed generating application {ctx.app_name} in environment {ctx.env_name}')
      raise e

    ymls = []

    ymls.append(Content(
        resource_type=ResourceType.YAML,
        data=stdout.decode('utf-8'),
        source='Helmfile'
    ))
    ctx_set(ctx, self.provides['content'], ymls)

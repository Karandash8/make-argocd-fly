import logging
import os
import shutil
import asyncio
import textwrap
import yaml
import yaml.composer
import yaml.parser
import yaml.scanner
import yaml.constructor
from pprint import pformat
from typing import Protocol, Iterable, Any
from deprecated import deprecated

try:
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  from yaml import SafeLoader

from make_argocd_fly.context import Context, ctx_get, ctx_set, resolve_expr
from make_argocd_fly.context.data import TemplatedResource, Resource
from make_argocd_fly.resource.viewer import ScopedViewer, ResourceType
from make_argocd_fly import default
from make_argocd_fly.resource.writer import AbstractWriter, GENERIC_WRITER, YAML_WRITER
from make_argocd_fly.param import ParamNames
from make_argocd_fly.config import get_config
from make_argocd_fly.cliparam import get_cli_params
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.exception import (UndefinedTemplateVariableError, TemplateRenderingError, InternalError,
                                       KustomizeError, PathDoesNotExistError, ConfigFileError, HelmfileError,
                                       OutputFilenameConstructionError)
from make_argocd_fly.util import extract_single_resource, get_app_rel_path, ensure_list, is_one_of
from make_argocd_fly.limits import RuntimeLimits
from make_argocd_fly.namegen import (K8sInfo, SourceInfo, K8sPolicy, SourcePolicy, Deduper, RoutingRules,
                                     KUSTOMIZE_BASENAMES, HELMFILE_BASENAMES)
from make_argocd_fly.type import PipelineType, NamingPolicyType, WriterType


log = logging.getLogger(__name__)


class Stage(Protocol):
  name: str
  requires: dict[str, str]
  provides: dict[str, str]

  async def run(self, ctx: Context) -> None: ...


@deprecated(version='v0.4.4', reason='`--print-vars` is deprecated, use `--dump-context` instead')
def print_vars_deprecated(app_name: str, env_name: str, vars_: dict) -> None:
  log.info(f'Variables for application {app_name} in environment {env_name}:\n{pformat(vars_)}')


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
    print_vars_deprecated(app_name, env_name, vars_)

  return vars_


def _discover_resources(viewer: ScopedViewer,
                        resource_types: list[ResourceType],
                        *,
                        search_subdirs: list[str] | None,
                        excludes: Iterable[str] | None) -> list[Resource]:
  out_resources = []
  for child in viewer.search_subresources(resource_types=resource_types,
                                          template=False,
                                          search_subdirs=search_subdirs,
                                          excludes=excludes):
    out_resources.append(Resource(resource_type=child.resource_type,
                                  data=child.content,
                                  origin=child.rel_path,
                                  source_path=child.rel_path))

  return out_resources


def _discover_templated_resources(viewer: ScopedViewer,
                                  resource_types: list[ResourceType],
                                  resolved_vars: dict,
                                  *,
                                  search_subdirs: list[str] | None,
                                  excludes: Iterable[str] | None) -> list[TemplatedResource]:
    out_templated_resources = []
    for child in viewer.search_subresources(resource_types=resource_types,
                                            template=True,
                                            search_subdirs=search_subdirs,
                                            excludes=excludes):
      out_templated_resources.append(TemplatedResource(resource_type=child.resource_type,
                                                       vars=resolved_vars,
                                                       data=child.content,
                                                       origin=child.rel_path,
                                                       source_path=child.rel_path))

    return out_templated_resources


def _discover_extra_resources(viewer: ScopedViewer,
                              resource_types: list[ResourceType],
                              *,
                              search_subdirs: list[str] | None,
                              excludes: Iterable[str] | None,
                              includes: Iterable[str] | None) -> list[Resource]:
    out_extra_resources = []
    for child in viewer.search_subresources(resource_types=resource_types,
                                            template=False,
                                            search_subdirs=search_subdirs,
                                            excludes=excludes,
                                            includes=includes):
      out_extra_resources.append(Resource(resource_type=child.resource_type,
                                          data=child.content,
                                          origin=child.rel_path,
                                          source_path=child.rel_path))

    return out_extra_resources


def _discover_templated_extra_resources(viewer: ScopedViewer,
                                        resource_types: list[ResourceType],
                                        resolved_vars: dict,
                                        *,
                                        search_subdirs: list[str] | None,
                                        excludes: Iterable[str] | None,
                                        includes: Iterable[str] | None) -> list[TemplatedResource]:
    out_templated_extra_resources = []
    for child in viewer.search_subresources(resource_types=resource_types,
                                            template=True,
                                            search_subdirs=search_subdirs,
                                            excludes=excludes,
                                            includes=includes):
      out_templated_extra_resources.append(TemplatedResource(resource_type=child.resource_type,
                                                             vars=resolved_vars,
                                                             data=child.content,
                                                             origin=child.rel_path,
                                                             source_path=child.rel_path))

    return out_templated_extra_resources


class DiscoverK8sSimpleApplication(Stage):
  name = 'DiscoverK8sSimpleApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)
    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    out_resources = _discover_resources(viewer,
                                        resource_types=[ResourceType.YAML],
                                        search_subdirs=None,
                                        excludes=exclude_rendering)
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=[ResourceType.YAML],
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=None,
                                                            excludes=exclude_rendering)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class DiscoverK8sKustomizeApplication(Stage):
  name = 'DiscoverK8sKustomizeApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    # Determine search_subdirs:
    # look for root-level "base" and "<env_name>" directories; if none exist, use None
    candidate_subdirs: list[str] = []

    if list(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY],
                                       name_pattern=r'^base$',
                                       depth=1)):
      candidate_subdirs.append('base')

    if list(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY],
                                       name_pattern=fr'^{ctx.env_name}$',
                                       depth=1)):
      candidate_subdirs.append(ctx.env_name)

    search_subdirs = candidate_subdirs or None

    non_k8s_files = ensure_list(ctx.params.non_k8s_files_to_render, ParamNames.NON_K8S_FILES_TO_RENDER)
    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)

    # 1) regular YAML resources (non-template), exclude both lists
    out_resources = _discover_resources(viewer,
                                        resource_types=[ResourceType.YAML],
                                        search_subdirs=search_subdirs,
                                        excludes=exclude_rendering + non_k8s_files)

    # 2) regular YAML templated resources, exclude both lists
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=[ResourceType.YAML],
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=search_subdirs,
                                                            excludes=exclude_rendering + non_k8s_files)

    all_file_types = [resource_type for resource_type in ResourceType if
                      (resource_type != ResourceType.DIRECTORY and
                       resource_type != ResourceType.DOES_NOT_EXIST)]

    # 3) extra resources: include only non_k8s_files_to_render (any file type), exclude exclude_rendering
    out_extra_resources = _discover_extra_resources(viewer,
                                                    resource_types=all_file_types,
                                                    search_subdirs=search_subdirs,
                                                    excludes=exclude_rendering,
                                                    includes=non_k8s_files)

    # 4) templated extra resources: include only non_k8s_files_to_render (any file type), exclude exclude_rendering
    out_templated_extra_resources = _discover_templated_extra_resources(viewer,
                                                                        resource_types=all_file_types,
                                                                        resolved_vars=resolved_vars,
                                                                        search_subdirs=search_subdirs,
                                                                        excludes=exclude_rendering,
                                                                        includes=non_k8s_files)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['extra_resources'], out_extra_resources)
    ctx_set(ctx, self.provides['templated_extra_resources'], out_templated_extra_resources)
    ctx_set(ctx, self.provides['tmp_dir'], os.path.join(config.tmp_dir, default.KUSTOMIZE_DIR))
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
      log.error(f'Missing kustomization.yml in the application directory. Skipping application {ctx.app_name} in environment {ctx.env_name}')
      raise InternalError()

    ctx_set(ctx, self.provides['kustomize_exec_dir'], kustomize_exec_dir)


class DiscoverK8sHelmfileApplication(Stage):
  name = 'DiscoverK8sHelmfileApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)
    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    out_resources = _discover_resources(viewer,
                                        resource_types=[ResourceType.YAML],
                                        search_subdirs=None,
                                        excludes=exclude_rendering)
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=[ResourceType.YAML],
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=None,
                                                            excludes=exclude_rendering)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['tmp_dir'], os.path.join(config.tmp_dir, default.HELMFILE_DIR))
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
        params = config.get_params(env_name, app_name)

        if params.parent_app:
          if (params.parent_app == ctx.app_name and
              ((params.parent_app_env is None and env_name == ctx.env_name) or
                (params.parent_app_env is not None and params.parent_app_env == ctx.env_name))):
            discovered_apps.append((env_name, app_name))

    out_templated_resources = []
    for env_name, app_name in discovered_apps:
      resolved_vars = _resolve_template_vars(env_name, app_name)

      try:
        out_templated_resources.append(TemplatedResource(
          resource_type=ResourceType.YAML,
          vars=resolved_vars,
          data=textwrap.dedent(resolved_vars['argocd_application_cr_template']),
          origin='Application',
          source_path=None,
        ))
      except TypeError:
        log.error(f'Error rendering Jinja template for application {ctx.app_name} in environment {ctx.env_name}. '
                  f'Ensure that the template is correctly defined in the config file.')
        raise ConfigFileError

    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)

    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class DiscoverGenericApplication(Stage):
  name = 'DiscoverGenericApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)
    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    all_file_types = [resource_type for resource_type in ResourceType if
                      (resource_type != ResourceType.DIRECTORY and
                       resource_type != ResourceType.DOES_NOT_EXIST)]

    out_resources = _discover_resources(viewer,
                                        resource_types=all_file_types,
                                        search_subdirs=None,
                                        excludes=exclude_rendering)
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=all_file_types,
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=None,
                                                            excludes=exclude_rendering)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class RenderTemplates(Stage):
  name = 'RenderTemplates'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    templated_resources = ctx_get(ctx, self.requires['templated_resources'])
    viewer = ctx_get(ctx, self.requires['viewer'])

    renderer = JinjaRenderer()
    renderer.set_resource_viewer(viewer)
    out_resources = []

    for template in templated_resources:
      renderer.set_template_vars(template.vars)
      renderer.set_template_origin(template.origin)

      try:
        result = renderer.render(template.data)

        out_resources.append(Resource(resource_type=template.resource_type,
                                      data=result,
                                      origin=template.origin,
                                      source_path=template.source_path))
      except (UndefinedTemplateVariableError, PathDoesNotExistError):
        log.error(f'Error rendering template {template.origin}')
        raise TemplateRenderingError(template.origin, ctx.app_name, ctx.env_name) from None

    ctx_set(ctx, self.provides['resources'], out_resources)


class SplitManifests(Stage):
  name = 'SplitManifests'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    in_resources: list[Resource] = resolve_expr(ctx, self.requires['resources'])

    out_resources = []
    for resource in in_resources:
      if resource.resource_type == ResourceType.YAML:
        for single in extract_single_resource(resource.data):
          out_resources.append(Resource(resource_type=ResourceType.YAML,
                                        data=single,
                                        origin=resource.origin,
                                        source_path=resource.source_path))
      else:
        out_resources.append(resource)

    ctx_set(ctx, self.provides['resources'], out_resources)


class ConvertToYaml(Stage):
  name = 'ConvertToYaml'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    in_resources: list[Resource] = resolve_expr(ctx, self.requires['resources'])
    out_resources: list[Resource] = []

    for resource in in_resources:
      if resource.resource_type == ResourceType.YAML:
        try:
          obj = yaml.load(resource.data, Loader=SafeLoader)
          out_resources.append(resource.with_yaml(obj))
        except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError, yaml.constructor.ConstructorError):
          log.warning(f'YAML parse failed in ConvertToYaml for origin={resource.origin} path={resource.source_path}; leaving as text')
          out_resources.append(resource)
      else:
        out_resources.append(resource)

    ctx_set(ctx, self.provides['resources'], out_resources)


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
    in_resources: list[Resource] = resolve_expr(ctx, self.requires['resources'])

    rules = RoutingRules(
      pipeline_kind=self.pipeline_kind,
      kustomize_cfg=set(resolve_expr(ctx, 'discovered.kustomize_config_files') or []),
      helmfile_cfg=set(resolve_expr(ctx, 'discovered.helmfile_config_files') or []),
    )

    app_rel = get_app_rel_path(ctx.env_name, ctx.app_name)
    dedupe = Deduper()
    out_resources: list[Resource] = []

    for res in sorted(in_resources, key=lambda r: (r.source_path or '', r.origin)):
      log.debug(f'Processing resource: origin={res.origin} path={res.source_path}')

      policy_key = self._route_policy(res, rules)
      src = SourceInfo.from_source_path(res.source_path)

      try:
        if policy_key == NamingPolicyType.K8S:
          k8s = K8sInfo.from_yaml_obj(res.yaml_obj)
          rel = self.k8s_policy.render(k8s=k8s, src=src)
        elif policy_key == NamingPolicyType.SOURCE:
          rel = self.src_policy.render(k8s=None, src=src)
        elif policy_key is None:
          log.warning(f'Skipping resource due to no naming policy found (origin={res.origin} path={res.source_path}) '
                      f'for application {ctx.app_name} in environment {ctx.env_name}')
          continue
        else:
          log.warning(f'Skipping resource due to unknown policy \'{policy_key}\' (origin={res.origin} path={res.source_path})'
                      f' for application {ctx.app_name} in environment {ctx.env_name}')
          continue
      except OutputFilenameConstructionError as e:
        log.warning(f'Failed to construct output filename (origin={res.origin} path={res.source_path})'
                    f' for application {ctx.app_name} in environment {ctx.env_name}: {e}')
        continue

      rel = dedupe.unique(rel)
      out_resources.append(res.with_output_path(os.path.join(app_rel, rel)))

    ctx_set(ctx, self.provides['resources'], out_resources)

  def _route_policy(self, res: Resource, rules: RoutingRules) -> str | None:
    # Generic pipeline: always name by source
    if rules.pipeline_kind == PipelineType.GENERIC:
      return NamingPolicyType.SOURCE if res.source_path is not None else None

    # K8s pipelines
    if rules.pipeline_kind == PipelineType.K8S_KUSTOMIZE:
      # SourcePolicy for kustomization and values files
      if res.source_path and (is_one_of(res.source_path, KUSTOMIZE_BASENAMES) or res.source_path in rules.kustomize_cfg):
        return NamingPolicyType.SOURCE
      return NamingPolicyType.K8S if res.writer_type == WriterType.K8S_YAML else NamingPolicyType.SOURCE

    if rules.pipeline_kind == PipelineType.K8S_HELMFILE:
      # SourcePolicy for helmfile
      if res.source_path and (is_one_of(res.source_path, HELMFILE_BASENAMES) or res.source_path in rules.helmfile_cfg):
        return NamingPolicyType.SOURCE
      return NamingPolicyType.K8S if res.writer_type == WriterType.K8S_YAML else NamingPolicyType.SOURCE

    if rules.pipeline_kind in (PipelineType.K8S_SIMPLE, PipelineType.K8S_APP_OF_APPS):
      return NamingPolicyType.K8S if res.writer_type == WriterType.K8S_YAML else None
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

  async def _write_one(self, writer: AbstractWriter, payload: Any, output_dir: str, ctx: Context, resource: Resource) -> None:
    async with self.limits.io_sem:
      path = os.path.join(output_dir, resource.output_path)
      if path in self._written:
        log.error(f'Duplicate output: {path}')
        raise InternalError()
      self._written.add(path)

      # Offload the blocking write to a thread, bounded by io_sem
      await asyncio.to_thread(writer.write, path, payload, ctx.env_name, ctx.app_name, resource.origin)

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    resources = ctx_get(ctx, self.requires['resources'])
    output_dir = ctx_get(ctx, self.requires['output_dir'])
    self._written = set()

    app_output_dir = os.path.join(output_dir, get_app_rel_path(ctx.env_name, ctx.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    try:
      async with asyncio.TaskGroup() as tg:
        for resource in sorted(resources, key=lambda r: r.output_path):
          if resource.output_path is None:
            log.error(f'Resource {resource.origin} passed to {self.name} stage without output_path')
            raise InternalError()

          # Disallow writing non-files
          if resource.resource_type in (ResourceType.DIRECTORY, ResourceType.DOES_NOT_EXIST):
            log.error(f'Cannot write resource of type {resource.resource_type.name} (origin={resource.origin})')
            raise InternalError()

          if resource.writer_type == WriterType.K8S_YAML:
            writer = YAML_WRITER
            payload = resource.yaml_obj
          else:
            writer = GENERIC_WRITER
            payload = resource.data

          tg.create_task(self._write_one(writer, payload, output_dir, ctx, resource))
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

    resources = []

    resources.append(Resource(resource_type=ResourceType.YAML,
                              data=stdout.decode('utf-8'),
                              origin='Kustomize',
                              source_path=None))
    ctx_set(ctx, self.provides['resources'], resources)


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

    resources = []

    resources.append(Resource(resource_type=ResourceType.YAML,
                              data=stdout.decode('utf-8'),
                              origin='Helmfile',
                              source_path=None))
    ctx_set(ctx, self.provides['resources'], resources)

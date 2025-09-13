import logging
import os
import shutil
import asyncio
import textwrap
from pprint import pformat
from typing import Protocol

from make_argocd_fly.context import Context, ctx_get, ctx_set, resolve_expr
from make_argocd_fly.context.data import Content, Template, OutputResource
from make_argocd_fly.resource.type import ResourceType
from make_argocd_fly import const
from make_argocd_fly.config import get_config
from make_argocd_fly.cliparam import get_cli_params
from make_argocd_fly.renderer import JinjaRendererFromViewer
from make_argocd_fly.resource.persistence import ResourcePersistence
from make_argocd_fly.exception import UndefinedTemplateVariableError, TemplateRenderingError, InternalError, KustomizeError, \
  MissingFileError, ConfigFileError
from make_argocd_fly.util import extract_single_resource, FilePathGenerator, get_app_rel_path


log = logging.getLogger(__name__)


class Stage(Protocol):
  name: str
  requires: dict[str, str]
  provides: dict[str, str]

  async def run(self, ctx: Context) -> None: ...


class DiscoverK8sSimpleApplication(Stage):
  name = 'DiscoverK8sSimpleApplication'
  requires = {'viewer': 'source.viewer'}
  provides = {'content': 'discover.content',
              'template': 'discover.template',
              'output_dir': 'discover.output_dir'}

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    cli_params = get_cli_params()
    app_params = get_config().get_params(ctx.env_name, ctx.app_name)
    viewer = ctx_get(ctx, self.requires['viewer'])

    if not isinstance(app_params.exclude_rendering, list):
      log.error(f'Application parameter {const.ParamNames.EXCLUDE_RENDERING} must be a list')
      raise InternalError()

    ymls = []
    viewer_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML], template=False))

    for child in viewer_children:
      if not any(child.element_rel_path.startswith(exclude) for exclude in app_params.exclude_rendering):
        ymls.append(Content(
          resource_type=ResourceType.YAML,
          data=child.content,
          source=child.element_rel_path,
        ))
      else:
        log.debug(f'Excluding file {child.element_rel_path}')
    ctx_set(ctx, self.provides['content'], ymls)

    templates = []
    viewer_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML], template=True))

    extra_vars = {
      'argocd_application_cr_template': const.ARGOCD_APPLICATION_CR_TEMPLATE,
      'argocd': const.ARGOCD_DEFAULTS,
      'env_name': ctx.env_name,
      'app_name': ctx.app_name
    }
    resolved_vars = config.get_vars(env_name=ctx.env_name, app_name=ctx.app_name, extra_vars=extra_vars)
    if cli_params.print_vars:
      log.info(f'Variables for application {ctx.app_name} in environment {ctx.env_name}:\n{pformat(resolved_vars)}')

    for child in viewer_children:
      if not any(child.element_rel_path.startswith(exclude) for exclude in app_params.exclude_rendering):
        templates.append(Template(
          resource_type=ResourceType.YAML,
          vars=resolved_vars,
          data=child.content,
          source=child.element_rel_path,
        ))
      else:
        log.debug(f'Excluding file {child.element_rel_path}')
    ctx_set(ctx, self.provides['template'], templates)

    ctx_set(ctx, self.provides['output_dir'], config.output_dir)


class DiscoverK8sKustomizeApplication(Stage):
  name = 'DiscoverK8sKustomizeApplication'
  requires = {'viewer': 'source.viewer'}
  provides = {'content': 'discover.content',
              'template': 'discover.template',
              'kustomize_exec_dir': 'discover.kustomize_exec_dir',
              'tmp_dir': 'discover.tmp_dir',
              'output_dir': 'discover.output_dir'}

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    cli_params = get_cli_params()
    app_params = get_config().get_params(ctx.env_name, ctx.app_name)
    viewer = ctx_get(ctx, self.requires['viewer'])

    if not isinstance(app_params.exclude_rendering, list):
      log.error(f'Application parameter {const.ParamNames.EXCLUDE_RENDERING} must be a list')
      raise InternalError()

    # TODO: this will not work if there is a directory named `base` in addition to the kustomize base
    search_subdirs = ['base', ctx.env_name] if list(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY],
                                                                               name_pattern='base$')) else None

    ymls = []
    viewer_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML], template=False,
                                                      search_subdirs=search_subdirs))

    for child in viewer_children:
      if not any(child.element_rel_path.startswith(exclude) for exclude in app_params.exclude_rendering):
        ymls.append(Content(
          resource_type=ResourceType.YAML,
          data=child.content,
          source=child.element_rel_path,
        ))
      else:
        log.debug(f'Excluding file {child.element_rel_path}')
    ctx_set(ctx, self.provides['content'], ymls)

    templates = []
    viewer_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML], template=True,
                                                      search_subdirs=search_subdirs))

    extra_vars = {
      'argocd_application_cr_template': const.ARGOCD_APPLICATION_CR_TEMPLATE,
      'argocd': const.ARGOCD_DEFAULTS,
      'env_name': ctx.env_name,
      'app_name': ctx.app_name
    }
    resolved_vars = config.get_vars(env_name=ctx.env_name, app_name=ctx.app_name, extra_vars=extra_vars)

    if cli_params.print_vars:
      log.info(f'Variables for application {ctx.app_name} in environment {ctx.env_name}:\n{pformat(resolved_vars)}')

    for child in viewer_children:
      if not any(child.element_rel_path.startswith(exclude) for exclude in app_params.exclude_rendering):
        templates.append(Template(
          resource_type=ResourceType.YAML,
          vars=resolved_vars,
          data=child.content,
          source=child.element_rel_path,
        ))
      else:
        log.debug(f'Excluding file {child.element_rel_path}')
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


class DiscoverK8sAppOfAppsApplication(Stage):
  name = 'DiscoverK8sAppOfAppsApplication'
  requires = {}
  provides = {'template': 'discover.template',
              'output_dir': 'discover.output_dir'}

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    cli_params = get_cli_params()

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

      extra_vars = {
        'argocd_application_cr_template': const.ARGOCD_APPLICATION_CR_TEMPLATE,
        '__application': {
          'application_name': '-'.join([os.path.basename(app_name), env_name]).replace('_', '-'),
          'path': os.path.join(os.path.basename(config.output_dir), env_name, app_name)
        },
        'argocd': const.ARGOCD_DEFAULTS,
        'env_name': env_name,
        'app_name': app_name
      }
      resolved_vars = config.get_vars(env_name=env_name, app_name=app_name, extra_vars=extra_vars)

      if cli_params.print_vars:
        log.info(f'Variables for application {ctx.app_name} in environment {ctx.env_name}:\n{pformat(resolved_vars)}')

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


class RenderTemplates(Stage):
  name = 'RenderTemplates'
  requires = {'template': 'discover.template', 'viewer': 'source.viewer'}
  provides = {'content': 'template.content'}

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    templates = ctx_get(ctx, self.requires['template'])
    viewer = ctx_get(ctx, self.requires['viewer'])

    # TODO: maybe do set_viewer instead
    renderer = JinjaRendererFromViewer(viewer)
    ymls = []

    for template in templates:
      renderer.set_template_vars(template.vars)

      # TODO: rename to set_source
      renderer.set_filename(template.source)

      try:
        result = renderer.render(template.data)

        ymls.append(Content(
          resource_type=ResourceType.YAML,
          data=result,
          source=template.source,
        ))

      except (UndefinedTemplateVariableError, MissingFileError):
        log.error(f'Error rendering template {template.source}')
        raise TemplateRenderingError(template.source, ctx.app_name, ctx.env_name) from None

    ctx_set(ctx, self.provides['content'], ymls)


class SplitManifests(Stage):
  name = 'SplitManifests'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    ymls = resolve_expr(ctx, self.requires['content'])

    split_ymls = []
    for yml in ymls:
      for single in extract_single_resource(yml.data):
        split_ymls.append(Content(
          resource_type=ResourceType.YAML,
          data=single,
          source=yml.source,
        ))

    ctx_set(ctx, self.provides['content'], split_ymls)


class GenerateManifestNames(Stage):
  name = 'GenerateManifestNames'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    ymls = ctx_get(ctx, self.requires['content'])

    files = []

    for resource in ymls:
      generator = FilePathGenerator(resource.data, resource.source)
      app_params = get_config().get_params(ctx.env_name, ctx.app_name)

      if not isinstance(app_params.non_k8s_files_to_render, list):
        log.error(f'Application parameter {const.ParamNames.NON_K8S_FILES_TO_RENDER} must be a list')
        raise InternalError()

      if any(resource.source.startswith(element) for element in app_params.non_k8s_files_to_render):
        files.append(OutputResource(
            resource_type=resource.resource_type,
            data=resource.data,
            source=resource.source,
            output_path=os.path.join(get_app_rel_path(ctx.env_name, ctx.app_name), generator.generate_from_source_file())
        ))
        continue

      try:
        files.append(OutputResource(
          resource_type=resource.resource_type,
          data=resource.data,
          source=resource.source,
          output_path=os.path.join(get_app_rel_path(ctx.env_name, ctx.app_name), generator.generate_from_k8s_resource())
        ))
      except ValueError:
        log.debug(f'Could not generate file path for resource {resource.source}. Skipping it.')

    ctx_set(ctx, self.provides['files'], files)


class WriteYamls(Stage):
  name = 'WriteYamls'
  provides = {}

  def __init__(self, requires: dict[str, str]) -> None:
    self.requires = requires

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    files = ctx_get(ctx, self.requires['files'])
    output_dir = ctx_get(ctx, self.requires['output_dir'])

    app_output_dir = os.path.join(output_dir, get_app_rel_path(ctx.env_name, ctx.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    writer = ResourcePersistence(output_dir, ctx.env_name, ctx.app_name)
    for output_resource in files:
      writer.store_resource(output_resource)

    await writer.write_resources()


class KustomizeBuild(Stage):
  name = 'KustomizeBuild'
  requires = {'kustomize_exec_dir': 'discover.kustomize_exec_dir', 'tmp_dir': 'discover.tmp_dir'}
  provides = {'content': 'kustomize.content'}

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    kustomize_exec_dir = ctx_get(ctx, self.requires['kustomize_exec_dir'])
    tmp_dir = ctx_get(ctx, self.requires['tmp_dir'])

    dir_path = os.path.join(tmp_dir, get_app_rel_path(ctx.env_name, ctx.app_name), kustomize_exec_dir)
    retries = 3

    for attempt in range(retries):
      proc = await asyncio.create_subprocess_exec(
        'kustomize', 'build', '--enable-helm', dir_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

      stdout, stderr = await proc.communicate()
      if proc.returncode != 0:
        log.error(f'Kustomize error: {stderr.decode("utf-8", "ignore")}')
        log.info(f'Retrying {attempt + 1}/{retries}')
        continue
      break
    else:
      raise KustomizeError(ctx.app_name, ctx.env_name)

    ymls = []

    ymls.append(Content(
        resource_type=ResourceType.YAML,
        data=stdout.decode('utf-8'),
        source='Kustomize'
    ))
    ctx_set(ctx, self.provides['content'], ymls)

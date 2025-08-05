import logging
import os
from abc import ABC, abstractmethod
import textwrap
import shutil
from pprint import pformat

from make_argocd_fly.resource.viewer import ResourceViewer, ResourceType
from make_argocd_fly import const
from make_argocd_fly.util import get_app_rel_path
from make_argocd_fly.config import get_config
from make_argocd_fly.cliparam import get_cli_params
from make_argocd_fly.exception import ConfigFileError
from make_argocd_fly.step import FindAppsStep, RenderYamlStep, RenderJinjaFromViewerStep, RenderJinjaFromMemoryStep, \
  WriteResourcesStep, ReadSourceStep, RunKustomizeStep
from make_argocd_fly.exception import ResourceViewerIsFake

log = logging.getLogger(__name__)


class AbstractApplication(ABC):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer) -> None:
    super().__init__()

    self.app_name = app_name
    self.env_name = env_name
    self.app_viewer = app_viewer
    self.config = get_config()
    self.cli_params = get_cli_params()

  @abstractmethod
  async def process(self) -> None:
    pass


class AppOfAppsApplication(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.find_apps_step = FindAppsStep()
    self.render_jinja_step = RenderJinjaFromMemoryStep()
    self.write_resources_step = WriteResourcesStep()

    log.debug(f'Created application {app_name} with {__class__.__name__} for environment {env_name}')

  async def process(self) -> None:
    log.debug(f'Starting to process application {self.app_name} in environment {self.env_name}')

    self.find_apps_step.configure(self.env_name, self.app_name)
    await self.find_apps_step.run()

    for (app_name, env_name) in self.find_apps_step.get_apps():
      extra_vars = {
        'argocd_application_cr_template': const.ARGOCD_APPLICATION_CR_TEMPLATE,
        '__application': {
          'application_name': '-'.join([os.path.basename(app_name), env_name]).replace('_', '-'),
          'path': os.path.join(os.path.basename(self.config.output_dir), env_name, app_name)
        },
        'argocd': const.ARGOCD_DEFAULTS,
        'env_name': env_name,
        'app_name': app_name
      }
      resolved_vars = self.config.get_vars(env_name=env_name, app_name=app_name, extra_vars=extra_vars)

      if self.cli_params.print_vars:
        log.info(f'Variables for application {self.app_name} in environment {self.env_name}:\n{pformat(resolved_vars)}')

      try:
        self.render_jinja_step.configure(self.env_name,
                                         self.app_name,
                                         textwrap.dedent(resolved_vars['argocd_application_cr_template']),
                                         resolved_vars)
      except TypeError:
        log.error(f'Error rendering Jinja template for application {self.app_name} in environment {self.env_name}. '
                  f'Ensure that the template is correctly defined in the config file.')
        raise ConfigFileError
      await self.render_jinja_step.run()

    log.debug(f'Generated resources for application {self.app_name} in environment {self.env_name}')

    # Clean up output directory for the application
    app_output_dir = os.path.join(self.config.output_dir, get_app_rel_path(self.env_name, self.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    self.write_resources_step.configure(self.config.output_dir, self.render_jinja_step.get_resources())
    await self.write_resources_step.run()
    log.info(f'Updated application {self.app_name} in environment {self.env_name}')


class SimpleApplication(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.render_yaml_step = RenderYamlStep()
    self.render_jinja_step = RenderJinjaFromViewerStep(app_viewer)
    self.write_resources_step = WriteResourcesStep()

    log.debug(f'Created application {app_name} with {__class__.__name__} for environment {env_name}')

  async def process(self) -> None:
    log.debug(f'Starting to process application {self.app_name} in environment {self.env_name}')

    extra_vars = {
      'argocd_application_cr_template': const.ARGOCD_APPLICATION_CR_TEMPLATE,
      'argocd': const.ARGOCD_DEFAULTS,
      'env_name': self.env_name,
      'app_name': self.app_name
    }
    resolved_vars = self.config.get_vars(env_name=self.env_name, app_name=self.app_name, extra_vars=extra_vars)

    if self.cli_params.print_vars:
      log.info(f'Variables for application {self.app_name} in environment {self.env_name}:\n{pformat(resolved_vars)}')

    yml_children = list(self.app_viewer.search_subresources(resource_types=[ResourceType.YAML]))
    self.render_yaml_step.configure(self.env_name, self.app_name, yml_children)
    await self.render_yaml_step.run()

    j2_children = list(self.app_viewer.search_subresources(resource_types=[ResourceType.JINJA2]))
    self.render_jinja_step.configure(self.env_name, self.app_name, j2_children, resolved_vars)
    await self.render_jinja_step.run()

    log.debug(f'Generated resources for application {self.app_name} in environment {self.env_name}')

    # Clean up output directory for the application
    app_output_dir = os.path.join(self.config.output_dir, get_app_rel_path(self.env_name, self.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    self.write_resources_step.configure(self.config.output_dir, self.render_yaml_step.get_resources() + self.render_jinja_step.get_resources())
    await self.write_resources_step.run()

    log.info(f'Updated application {self.app_name} in environment {self.env_name}')


class KustomizeApplication(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.render_yaml_step = RenderYamlStep()
    self.render_jinja_step = RenderJinjaFromViewerStep(app_viewer)
    self.tmp_write_resources_step = WriteResourcesStep()
    self.tmp_read_source_step = ReadSourceStep()
    self.run_kustomize_step = RunKustomizeStep()
    self.write_resources_step = WriteResourcesStep()

    log.debug(f'Created application {app_name} with {__class__.__name__} for environment {env_name}')

  async def process(self) -> None:
    log.debug(f'Starting to process application {self.app_name} in environment {self.env_name}')

    extra_vars = {
      'argocd_application_cr_template': const.ARGOCD_APPLICATION_CR_TEMPLATE,
      'argocd': const.ARGOCD_DEFAULTS,
      'env_name': self.env_name,
      'app_name': self.app_name
    }
    resolved_vars = self.config.get_vars(env_name=self.env_name, app_name=self.app_name, extra_vars=extra_vars)

    if self.cli_params.print_vars:
      log.info(f'Variables for application {self.app_name} in environment {self.env_name}:\n{pformat(resolved_vars)}')

    search_subdirs = ['base', self.env_name] if list(self.app_viewer.search_subresources(resource_types=[ResourceType.DIRECTORY],
                                                                                         name_pattern='base$')) else None

    yml_children = list(self.app_viewer.search_subresources(resource_types=[ResourceType.YAML], search_subdirs=search_subdirs))
    self.render_yaml_step.configure(self.env_name, self.app_name, yml_children)
    await self.render_yaml_step.run()

    j2_children = list(self.app_viewer.search_subresources(resource_types=[ResourceType.JINJA2], search_subdirs=search_subdirs))
    self.render_jinja_step.configure(self.env_name, self.app_name, j2_children, resolved_vars)
    await self.render_jinja_step.run()

    self.tmp_write_resources_step.configure(self.config.tmp_dir, self.render_yaml_step.get_resources() + self.render_jinja_step.get_resources())
    await self.tmp_write_resources_step.run()

    self.tmp_read_source_step.configure(os.path.join(self.config.tmp_dir, get_app_rel_path(self.env_name, self.app_name)))
    await self.tmp_read_source_step.run()

    self.run_kustomize_step.configure(self.env_name, self.app_name, self.tmp_read_source_step.get_viewer())
    await self.run_kustomize_step.run()

    log.debug(f'Generated resources for application {self.app_name} in environment {self.env_name}')

    # Clean up output directory for the application
    app_output_dir = os.path.join(self.config.output_dir, get_app_rel_path(self.env_name, self.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    self.write_resources_step.configure(self.config.output_dir, self.run_kustomize_step.get_resources())
    await self.write_resources_step.run()

    log.info(f'Updated application {self.app_name} in environment {self.env_name}')


async def application_factory(env_name: str, app_name: str, source_path: str) -> AbstractApplication:
  read_source_step = ReadSourceStep()
  read_source_step.configure(source_path)

  await read_source_step.run()
  viewer = read_source_step.get_viewer()

  try:
    kustomize_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML, ResourceType.JINJA2],
                                                         name_pattern='kustomization|Kustomization'))

    if kustomize_children:
      return KustomizeApplication(app_name, env_name, viewer)
    else:
      return SimpleApplication(app_name, env_name, viewer)
  except ResourceViewerIsFake:
    return AppOfAppsApplication(app_name, env_name, viewer)

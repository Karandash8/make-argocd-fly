import logging
import os
import asyncio
from abc import ABC, abstractmethod

from make_argocd_fly.config import get_config
from make_argocd_fly.renderer import DummyRenderer, JinjaRenderer
from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.utils import extract_single_resource, get_filename_elements, generate_filename, get_app_rel_path

log = logging.getLogger(__name__)


class AbstractStep(ABC):
    @abstractmethod
    async def run(self) -> None:
        pass


class FindAppsStep(AbstractStep):
  def __init__(self) -> None:
    self.config = get_config()
    self.apps = []

  def configure(self, app_deployer_name: str, app_deployer_env_name: str) -> None:
    self.app_deployer_name = app_deployer_name
    self.app_deployer_env_name = app_deployer_env_name

  async def run(self) -> None:
    if not self.app_deployer_name or not self.app_deployer_env_name:
      log.error('Step is not configured')
      raise

    for env_name, env_data in self.config.get_envs().items():
      if 'apps' not in env_data:
        log.error('No apps defined in environment {}'.format(env_name))
        continue

      for app_name in env_data['apps'].keys():
        app_params = self.config.get_app_params(env_name, app_name)

        if 'app_deployer' in app_params:
          if (self.app_deployer_name == app_params['app_deployer'] and
              (('app_deployer_env' not in app_params and env_name == self.app_deployer_env_name) or
               ('app_deployer_env' in app_params and self.app_deployer_env_name == app_params['app_deployer_env']))):
            self.apps.append((app_name, env_name))

  def get_apps(self) -> list:
    return self.apps


class BaseResourceGenerationStep(AbstractStep):
  def __init__(self) -> None:
    self.resources = []

  def _generate_file_path(self, resource_yml: str, source_filename: str = None, element_rel_path: str = '.') -> str:
    app_params = get_config().get_app_params(self.env_name, self.app_name)

    filename_elements = get_filename_elements(resource_yml)
    if not filename_elements:
      if source_filename and 'non_k8s_files_to_render' in app_params and source_filename in app_params['non_k8s_files_to_render']:
        filename_elements = [os.path.basename(source_filename.split('.')[0])]
      else:
        raise ValueError("Filename elements could not be determined")

    if 'exclude_rendering' in app_params:
      for exclude in app_params['exclude_rendering']:
        if element_rel_path.startswith(exclude):
          log.debug("Excluded rendering for file {}".format(element_rel_path))
          raise ValueError("Excluded rendering for file {}".format(element_rel_path))

    return os.path.join(
      get_app_rel_path(self.env_name, self.app_name),
      os.path.dirname(element_rel_path),
      generate_filename(filename_elements)
    )

  def get_resources(self) -> list:
    return self.resources


class RenderYamlStep(BaseResourceGenerationStep):
  def __init__(self) -> None:
    super().__init__()
    self.renderer = DummyRenderer()

  def configure(self, yml_children: list, app_name: str, env_name: str) -> None:
    self.yml_children = yml_children
    self.app_name = app_name
    self.env_name = env_name

  async def run(self) -> None:
    for yml_child in self.yml_children:
      try:
        result = self.renderer.render(yml_child.content)

        for resource_yml in extract_single_resource(result):
          try:
            file_path = self._generate_file_path(resource_yml, yml_child.name, yml_child.element_rel_path)
            self.resources.append((file_path, resource_yml))
          except ValueError:
            pass
      except Exception as e:
        log.error('Error rendering yaml: {}'.format(e))
        raise


class RenderJinjaFromViewerStep(BaseResourceGenerationStep):
  def __init__(self, viewer: ResourceViewer) -> None:
    super().__init__()
    self.renderer = JinjaRenderer(viewer)

  def configure(self, j2_children: list, app_name: str, env_name: str, vars: dict = {}) -> None:
    self.j2_children = j2_children
    self.app_name = app_name
    self.env_name = env_name
    self.vars = vars

  async def run(self) -> None:
    for j2_child in self.j2_children:
      try:
        self.renderer.set_template_vars(self.vars)
        self.renderer.set_filename(j2_child.element_rel_path)
        result = self.renderer.render(j2_child.content)

        for resource_yml in extract_single_resource(result):
          try:
            file_path = self._generate_file_path(resource_yml, j2_child.name, j2_child.element_rel_path)
            self.resources.append((file_path, resource_yml))
          except ValueError:
            pass
      except Exception as e:
        log.error('Error rendering template {}: {}'.format(j2_child.element_rel_path, e))
        raise


class RenderJinjaFromMemoryStep(BaseResourceGenerationStep):
  def __init__(self) -> None:
    super().__init__()
    self.renderer = JinjaRenderer()

  def configure(self, template: str, app_name: str, env_name: str, vars: dict = {}) -> None:
    self.template = template
    self.app_name = app_name
    self.env_name = env_name
    self.vars = vars

  async def run(self) -> None:
    try:
      self.renderer.set_template_vars(self.vars)
      result = self.renderer.render(self.template)

      for resource_yml in extract_single_resource(result):
        try:
          file_path = self._generate_file_path(resource_yml)
          self.resources.append((file_path, resource_yml))
        except ValueError:
          pass
    except Exception:
      log.error('Error rendering template Application for application {} in environment {}'.format(self.app_name, self.env_name))
      raise


class RunKustomizeStep(BaseResourceGenerationStep):
  def __init__(self) -> None:
    super().__init__()
    self.dir_path = None

  def configure(self, viewer: ResourceViewer, app_name: str, env_name: str) -> None:
    self.viewer = viewer
    self.app_name = app_name
    self.env_name = env_name

    kustomization_children = self.viewer.get_files_children('kustomization.yml')
    kustomization_locations = [
      os.path.join(self.env_name, 'kustomization.yml'),
      os.path.join('base', 'kustomization.yml'),
      'kustomization.yml'
    ]
    for location in kustomization_locations:
      if location in [child.element_rel_path for child in kustomization_children]:
        self.dir_path = os.path.join(self.viewer.root_element_abs_path, os.path.dirname(location))
        break
    else:
      log.error('Missing kustomization.yml in the application directory. Skipping application')

  async def run(self) -> None:
    retries = 3

    if not self.dir_path:
      log.error('Step is not configured')
      raise

    for attempt in range(retries):
      proc = await asyncio.create_subprocess_shell(
        'kustomize build --enable-helm {}'.format(self.dir_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

      stdout, stderr = await proc.communicate()
      if stderr:
        log.error('Kustomize error: {}'.format(stderr))
        log.info('Retrying {}/{}'.format(attempt + 1, retries))
        continue
      break
    else:
      raise Exception('Kustomize execution failed for application {} in environment {}'.format(self.app_name, self.env_name))

    for resource_yml in extract_single_resource(stdout.decode("utf-8")):
      try:
        file_path = self._generate_file_path(resource_yml)
        self.resources.append((file_path, resource_yml))
      except ValueError:
        pass


class WriteResourcesStep(AbstractStep):
  def __init__(self) -> None:
    pass

  def configure(self, output_dir_abs_path: str, resources_to_write: list) -> None:
    self.writer = ResourceWriter(output_dir_abs_path)

    for path, content in resources_to_write:
      self.writer.store_resource(path, content)

  async def run(self) -> None:
    await self.writer.write_resources()


class ReadSourceStep(AbstractStep):
  def __init__(self) -> None:
    pass

  def configure(self, input_dir_abs_path: str) -> None:
    self.viewer = ResourceViewer(input_dir_abs_path)

  async def run(self) -> None:
    self.viewer.build()

  def get_viewer(self) -> ResourceViewer:
    return self.viewer

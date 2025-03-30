import logging
import os
import asyncio
from abc import ABC, abstractmethod
import yaml
import yaml.composer
import yaml.parser
import yaml.scanner
try:
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  from yaml import SafeLoader

from make_argocd_fly.consts import AppParamsNames
from make_argocd_fly.config import get_config
from make_argocd_fly.renderer import YamlRenderer, JinjaRenderer
from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.utils import extract_single_resource, FilePathGenerator, get_app_rel_path
from make_argocd_fly.exceptions import UndefinedTemplateVariableError, TemplateRenderingError, InternalError

log = logging.getLogger(__name__)


class YamlLoader(SafeLoader):
  pass


class AbstractStep(ABC):
    @abstractmethod
    async def run(self) -> None:
        pass


class FindAppsStep(AbstractStep):
  def __init__(self) -> None:
    self.config = get_config()
    self.apps = []
    self.parent_app_name = None
    self.parent_app_env_name = None

  def configure(self, parent_app_env_name: str, parent_app_name: str) -> None:
    self.parent_app_env_name = parent_app_env_name
    self.parent_app_name = parent_app_name

  async def run(self) -> None:
    if not self.parent_app_name or not self.parent_app_env_name:
      log.error('Step is not configured')
      raise InternalError

    for env_name, env_data in self.config.get_envs().items():
      if 'apps' in env_data:
        for app_name in env_data['apps'].keys():
          app_params = self.config.get_app_params(env_name, app_name)

          if AppParamsNames.APP_DEPLOYER in app_params:
            if (self.parent_app_name == app_params[AppParamsNames.APP_DEPLOYER] and
                ((AppParamsNames.APP_DEPLOYER_ENV not in app_params and env_name == self.parent_app_env_name) or
                (AppParamsNames.APP_DEPLOYER_ENV in app_params and self.parent_app_env_name == app_params[AppParamsNames.APP_DEPLOYER_ENV]))):
              self.apps.append((app_name, env_name))

  def get_apps(self) -> list:
    return self.apps


class BaseResourceGenerationStep(AbstractStep):
  def __init__(self) -> None:
    self.resources = []
    self.env_name = None
    self.app_name = None

  def _generate_file_path(self, resource_yml: str, source_file_path: str = None) -> str:
    if not self.env_name or not self.app_name:
      log.error('Step is not configured')
      raise InternalError

    app_params = get_config().get_app_params(self.env_name, self.app_name)
    generator = FilePathGenerator(resource_yml, source_file_path)

    # TODO use @singledispatch here
    if source_file_path and AppParamsNames.NON_K8S_FILES_TO_RENDER in app_params:
      if type(app_params[AppParamsNames.NON_K8S_FILES_TO_RENDER]) is not list:
        log.error('Application parameter {} must be a list'.format(AppParamsNames.NON_K8S_FILES_TO_RENDER))
        raise InternalError

      for element in app_params[AppParamsNames.NON_K8S_FILES_TO_RENDER]:
        if source_file_path.startswith(element):
          return os.path.join(get_app_rel_path(self.env_name, self.app_name), generator.generate_from_source_file())

    # TODO use @singledispatch here
    if source_file_path and AppParamsNames.EXCLUDE_RENDERING in app_params:
      if type(app_params[AppParamsNames.EXCLUDE_RENDERING]) is not list:
        log.error('Application parameter {} must be a list'.format(AppParamsNames.EXCLUDE_RENDERING))
        raise InternalError

      for element in app_params[AppParamsNames.EXCLUDE_RENDERING]:
        if source_file_path.startswith(element):
          log.debug('Exclude rendering for file {}'.format(source_file_path))
          raise ValueError

    return os.path.join(get_app_rel_path(self.env_name, self.app_name), generator.generate_from_k8s_resource())

  def get_resources(self) -> list:
    return self.resources


class RenderYamlStep(BaseResourceGenerationStep):
  def __init__(self) -> None:
    super().__init__()
    self.renderer = YamlRenderer()

  def configure(self, env_name: str, app_name: str, yml_children: list[ResourceViewer]) -> None:
    self.env_name = env_name
    self.app_name = app_name
    self.yml_children = yml_children

  async def run(self) -> None:
    if not self.env_name or not self.app_name:
      log.error('Step is not configured')
      raise InternalError

    for yml_child in self.yml_children:
      resource_source = os.path.join(yml_child.root_element_abs_path, yml_child.element_rel_path)

      try:
        result = self.renderer.render(yml_child.content)

        for resource_yml in extract_single_resource(result):
          try:
            file_path = self._generate_file_path(resource_yml, yml_child.element_rel_path)
            self.resources.append((file_path, yaml.load(resource_yml, Loader=YamlLoader)))
          except ValueError:
            pass
      except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError):
        log.error('Error building YAML')
        log.error('Error rendering template {}'.format(resource_source))
        log.debug('YAML content:\n{}'.format(resource_yml))
        raise TemplateRenderingError(resource_source, self.app_name, self.env_name) from None


class RenderJinjaFromViewerStep(BaseResourceGenerationStep):
  def __init__(self, viewer: ResourceViewer) -> None:
    super().__init__()
    self.renderer = JinjaRenderer(viewer)

  def configure(self, env_name: str, app_name: str, j2_children: list[ResourceViewer], vars: dict = {}) -> None:
    self.env_name = env_name
    self.app_name = app_name
    self.j2_children = j2_children
    self.vars = vars

  async def run(self) -> None:
    if not self.env_name or not self.app_name:
      log.error('Step is not configured')
      raise InternalError

    for j2_child in self.j2_children:
      resource_source = os.path.join(j2_child.root_element_abs_path, j2_child.element_rel_path)

      try:
        self.renderer.set_template_vars(self.vars)
        self.renderer.set_filename(j2_child.element_rel_path)
        result = self.renderer.render(j2_child.content)

        for resource_yml in extract_single_resource(result):
          try:
            file_path = self._generate_file_path(resource_yml, j2_child.element_rel_path)
            self.resources.append((file_path, yaml.load(resource_yml, Loader=YamlLoader)))
          except ValueError:
            pass
      except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError):
        log.error('Error building YAML')
        log.error('Error rendering template {}'.format(resource_source))
        log.debug('YAML content:\n{}'.format(resource_yml))
        raise TemplateRenderingError(resource_source, self.app_name, self.env_name) from None
      except UndefinedTemplateVariableError:
        log.error('Error rendering template {}'.format(resource_source))
        raise TemplateRenderingError(resource_source, self.app_name, self.env_name) from None


class RenderJinjaFromMemoryStep(BaseResourceGenerationStep):
  def __init__(self) -> None:
    super().__init__()
    self.renderer = JinjaRenderer()

  def configure(self, env_name: str, app_name: str, template: str, vars: dict = {}) -> None:
    self.env_name = env_name
    self.app_name = app_name
    self.template = template
    self.vars = vars

  async def run(self) -> None:
    if not self.env_name or not self.app_name:
      log.error('Step is not configured')
      raise InternalError

    resource_source = 'ArgoCD Application CustomResource'
    try:
      self.renderer.set_template_vars(self.vars)
      self.renderer.set_filename(resource_source)
      result = self.renderer.render(self.template)

      for resource_yml in extract_single_resource(result):
        try:
          file_path = self._generate_file_path(resource_yml)
          self.resources.append((file_path, yaml.load(resource_yml, Loader=YamlLoader)))
        except ValueError:
          pass
    except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError):
        log.error('Error building YAML')
        log.error('Error rendering template {}'.format(resource_source))
        log.debug('YAML content:\n{}'.format(resource_yml))
        raise TemplateRenderingError(resource_source, self.app_name, self.env_name) from None
    except UndefinedTemplateVariableError:
      log.error('Error rendering template {}'.format(resource_source))
      raise TemplateRenderingError(resource_source, self.app_name, self.env_name) from None


class RunKustomizeStep(BaseResourceGenerationStep):
  def __init__(self) -> None:
    super().__init__()
    self.dir_path = None

  def configure(self, env_name: str, app_name: str, viewer: ResourceViewer) -> None:
    self.env_name = env_name
    self.app_name = app_name
    self.viewer = viewer

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
      raise InternalError

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

    resource_source = 'Kustomize'
    try:
      for resource_yml in extract_single_resource(stdout.decode("utf-8")):
        try:
          file_path = self._generate_file_path(resource_yml)
          self.resources.append((file_path, yaml.load(resource_yml, Loader=YamlLoader)))
        except ValueError:
          pass
    except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError):
      log.error('Error building YAML')
      log.error('Error rendering template {}'.format(resource_source))
      log.debug('YAML content:\n{}'.format(resource_yml))
      raise TemplateRenderingError(resource_source, self.app_name, self.env_name) from None


class WriteResourcesStep(AbstractStep):
  def __init__(self) -> None:
    pass

  def configure(self, output_dir_abs_path: str, resources_to_write: list) -> None:
    self.writer = ResourceWriter(output_dir_abs_path)

    for path, yaml_object in resources_to_write:
      self.writer.store_resource(path, yaml_object)

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

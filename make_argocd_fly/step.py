import logging
import os
import asyncio
from abc import ABC, abstractmethod

from make_argocd_fly import const
from make_argocd_fly.config import get_config
from make_argocd_fly.renderer import YamlRenderer, JinjaRenderer, JinjaRendererFromViewer
from make_argocd_fly.resource.viewer import ResourceViewer
from make_argocd_fly.resource.type import ResourceType
from make_argocd_fly.resource.data import OutputResource
from make_argocd_fly.resource.persistence import ResourcePersistence
from make_argocd_fly.util import extract_single_resource, FilePathGenerator, get_app_rel_path
from make_argocd_fly.exception import UndefinedTemplateVariableError, TemplateRenderingError, InternalError, KustomizeError, \
  MissingFileError

log = logging.getLogger(__name__)


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
      log.error(f'{self.__class__.__name__} step is not configured')
      raise InternalError()

    for env_name in self.config.list_envs():
      for app_name in self.config.list_apps(env_name):
          app_params = self.config.get_app_params_deprecated(env_name, app_name)
          if not app_params:
            app_params = self.config.get_params(env_name, app_name)

            if app_params.parent_app:
              if (app_params.parent_app == self.parent_app_name and
                  ((app_params.parent_app_env is None and env_name == self.parent_app_env_name) or
                   (app_params.parent_app_env is not None and app_params.parent_app_env == self.parent_app_env_name))):
                self.apps.append((app_name, env_name))
          else:
            # DEPRECATED
            if const.AppParamsNames.APP_DEPLOYER in app_params:
              if (self.parent_app_name == app_params[const.AppParamsNames.APP_DEPLOYER] and
                  ((const.AppParamsNames.APP_DEPLOYER_ENV not in app_params and env_name == self.parent_app_env_name) or
                  (const.AppParamsNames.APP_DEPLOYER_ENV in app_params and
                   self.parent_app_env_name == app_params[const.AppParamsNames.APP_DEPLOYER_ENV]))):
                self.apps.append((app_name, env_name))

  def get_apps(self) -> list:
    return self.apps


class BaseResourceGenerationStep(AbstractStep):
  def __init__(self) -> None:
    self.output_resources = []
    self.env_name = None
    self.app_name = None

  def get_output_resources(self) -> list[OutputResource]:
    return self.output_resources


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
      log.error(f'{self.__class__.__name__} step is not configured')
      raise InternalError()

    for yml_child in self.yml_children:
      result = self.renderer.render(yml_child.content)

      for resource_yml in extract_single_resource(result):
        self.output_resources.append(OutputResource(
            app_name=self.app_name,
            env_name=self.env_name,
            resource_type=ResourceType.YAML,
            data=resource_yml,
            source_resource_path=yml_child.element_rel_path,
        ))


class RenderJinjaFromViewerStep(BaseResourceGenerationStep):
  def __init__(self, viewer: ResourceViewer) -> None:
    super().__init__()
    self.renderer = JinjaRendererFromViewer(viewer)

  def configure(self, env_name: str, app_name: str, j2_children: list[ResourceViewer], vars: dict = {}) -> None:
    self.env_name = env_name
    self.app_name = app_name
    self.j2_children = j2_children
    self.vars = vars

  async def run(self) -> None:
    if not self.env_name or not self.app_name:
      log.error(f'{self.__class__.__name__} step is not configured')
      raise InternalError()

    for j2_child in self.j2_children:
      resource_source = os.path.join(j2_child.root_element_abs_path, j2_child.element_rel_path)

      self.renderer.set_template_vars(self.vars)
      self.renderer.set_filename(j2_child.element_rel_path)
      try:
        result = self.renderer.render(j2_child.content)

        for resource_yml in extract_single_resource(result):
          self.output_resources.append(OutputResource(
              app_name=self.app_name,
              env_name=self.env_name,
              resource_type=ResourceType.YAML,
              data=resource_yml,
              source_resource_path=j2_child.element_rel_path,
          ))
      except (UndefinedTemplateVariableError, MissingFileError):
        log.error(f'Error rendering template {resource_source}')
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
      log.error(f'{self.__class__.__name__} step is not configured')
      raise InternalError()

    resource_source = 'ArgoCD Application CustomResource'

    self.renderer.set_template_vars(self.vars)
    try:
      result = self.renderer.render(self.template)

      for resource_yml in extract_single_resource(result):
        self.output_resources.append(OutputResource(
            app_name=self.app_name,
            env_name=self.env_name,
            resource_type=ResourceType.YAML,
            data=resource_yml,
            source_resource_path=resource_source,
        ))
    except (UndefinedTemplateVariableError, MissingFileError):
      log.error(f'Error rendering template {resource_source}')
      raise TemplateRenderingError(resource_source, self.app_name, self.env_name) from None


class RunKustomizeStep(BaseResourceGenerationStep):
  def __init__(self) -> None:
    super().__init__()
    self.dir_path = None

  def configure(self, env_name: str, app_name: str, viewer: ResourceViewer) -> None:
    self.env_name = env_name
    self.app_name = app_name
    self.viewer = viewer

    if list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                       name_pattern='kustomization|Kustomization',
                                       search_subdirs=[self.env_name],
                                       depth=1)):
      self.dir_path = os.path.join(self.viewer.root_element_abs_path, self.env_name)
    elif list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                         name_pattern='kustomization|Kustomization',
                                         search_subdirs=['base'],
                                         depth=1)):
      self.dir_path = os.path.join(self.viewer.root_element_abs_path, 'base')
    elif list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                         name_pattern='kustomization|Kustomization',
                                         depth=1)):
      self.dir_path = self.viewer.root_element_abs_path
    else:
      log.error(f'Missing kustomization.yml in the application directory. Skipping application {self.app_name} in environment {self.env_name}')

  async def run(self) -> None:
    retries = 3

    if not self.dir_path:
      log.error(f'{self.__class__.__name__} step is not configured')
      raise InternalError()

    for attempt in range(retries):
      proc = await asyncio.create_subprocess_exec(
        'kustomize', 'build', '--enable-helm', self.dir_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

      stdout, stderr = await proc.communicate()
      if proc.returncode != 0:
        log.error(f'Kustomize error: {stderr.decode("utf-8", "ignore")}')
        log.info(f'Retrying {attempt + 1}/{retries}')
        continue
      break
    else:
      raise KustomizeError(self.app_name, self.env_name)

    for resource_yml in extract_single_resource(stdout.decode('utf-8')):
      self.output_resources.append(OutputResource(
          app_name=self.app_name,
          env_name=self.env_name,
          resource_type=ResourceType.YAML,
          data=resource_yml,
          source_resource_path='Kustomize',
      ))


class FileNameGeneratorStep(AbstractStep):
  def __init__(self) -> None:
    self.resources = None
    self.output_resources = []

  def configure(self, resources: list[OutputResource]) -> None:
    self.resources = resources

  # flake8: noqa: C901
  async def run(self) -> None:
    if not isinstance(self.resources, list):
      log.error(f'{self.__class__.__name__} step is not configured')
      raise InternalError()

    for resource in self.resources:
      generator = FilePathGenerator(resource.data, resource.source_resource_path)
      app_params = get_config().get_app_params_deprecated(resource.env_name, resource.app_name)
      if not app_params:
        app_params = get_config().get_params(resource.env_name, resource.app_name)

        if not isinstance(app_params.non_k8s_files_to_render, list):
          log.error(f'Application parameter {const.ParamNames.NON_K8S_FILES_TO_RENDER} must be a list')
          raise InternalError()

        if any(resource.source_resource_path.startswith(element) for element in app_params.non_k8s_files_to_render):
          resource.output_resource_path = os.path.join(get_app_rel_path(resource.env_name, resource.app_name), generator.generate_from_source_file())

          self.output_resources.append(resource)
          continue

        if not isinstance(app_params.exclude_rendering, list):
          log.error(f'Application parameter {const.ParamNames.EXCLUDE_RENDERING} must be a list')
          raise InternalError()

        if any(resource.source_resource_path.startswith(exclude) for exclude in app_params.exclude_rendering):
          log.debug(f'Excluding file {resource.source_resource_path}')
          continue
      else:
        # DEPRECATED
        if resource.source_resource_path and const.AppParamsNames.NON_K8S_FILES_TO_RENDER in app_params:
          if not isinstance(app_params[const.AppParamsNames.NON_K8S_FILES_TO_RENDER], list):
            log.error(f'Application parameter {const.AppParamsNames.NON_K8S_FILES_TO_RENDER} must be a list')
            raise InternalError()

          if any(resource.source_resource_path.startswith(element) for element in app_params[const.AppParamsNames.NON_K8S_FILES_TO_RENDER]):
            resource.output_resource_path = os.path.join(get_app_rel_path(resource.env_name, resource.app_name),
                                                         generator.generate_from_source_file())

            self.output_resources.append(resource)
            continue

        if resource.source_resource_path and const.AppParamsNames.EXCLUDE_RENDERING in app_params:
          if not isinstance(app_params[const.AppParamsNames.EXCLUDE_RENDERING], list):
            log.error(f'Application parameter {const.AppParamsNames.EXCLUDE_RENDERING} must be a list')
            raise InternalError()

          if any(resource.source_resource_path.startswith(exclude) for exclude in app_params[const.AppParamsNames.EXCLUDE_RENDERING]):
            log.debug(f'Excluding file {resource.source_resource_path}')
            continue

      try:
        resource.output_resource_path = os.path.join(get_app_rel_path(resource.env_name, resource.app_name), generator.generate_from_k8s_resource())
        self.output_resources.append(resource)
      except ValueError:
        log.debug(f'Could not generate file path for resource {resource.source_resource_path}. Skipping it.')

  def get_output_resources(self) -> list[OutputResource]:
    return self.output_resources


class WriteResourcesStep(AbstractStep):
  def configure(self, output_dir_abs_path: str, output_resources: list[OutputResource]) -> None:
    self.writer = ResourcePersistence(output_dir_abs_path)

    for output_resource in output_resources:
      self.writer.store_resource(output_resource)

  async def run(self) -> None:
    await self.writer.write_resources()


class ReadSourceStep(AbstractStep):
  def configure(self, input_dir_abs_path: str) -> None:
    self.resource_path = input_dir_abs_path

  async def run(self) -> None:
    self.viewer = ResourceViewer(self.resource_path)

  def get_viewer(self) -> ResourceViewer:
    return self.viewer

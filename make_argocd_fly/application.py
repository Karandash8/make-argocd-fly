import logging
import os
from abc import ABC, abstractmethod
import subprocess
import shutil
import textwrap

from mergedeep import merge

from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.utils import extract_dir_rel_path, multi_resource_parser
from make_argocd_fly.config import get_config

log = logging.getLogger(__name__)


class AbstractApplication(ABC):
  def __init__(self, app_name: str, env_name: str, template_vars: dict, app_viewer: ResourceViewer = None) -> None:
    super().__init__()

    self.app_name = app_name
    self.env_name = env_name
    self.template_vars = template_vars
    self.app_viewer = app_viewer

    log.debug('Created application {} in environment {}'.format(app_name, env_name))

  @abstractmethod
  def generate_resources(self) -> str:
    pass

  def get_app_rel_path(self) -> str:
    return os.path.join(self.env_name, self.app_name)


class AppOfApps(AbstractApplication):
  APPLICATION_RESOUCE_TEMPLATE = '''\
    apiVersion: argoproj.io/v1alpha1
    kind: Application
    metadata:
      name: {{ __application.application_name }}
      namespace: {{ argocd.namespace }}
      finalizers:
        - resources-finalizer.argocd.argoproj.io
    spec:
      project: {{ __application.project }}
      source:
        repoURL: {{ argocd.repo_url }}
        targetRevision: {{ argocd.target_revision }}
        path: {{ __application.path }}
      destination:
        server: {{ argocd.api_server }}
        namespace: {{ __application.destination_namespace }}
      syncPolicy:
        automated:
          selfHeal: true
          prune: true
          allowEmpty: true
        # https://www.arthurkoziel.com/fixing-argocd-crd-too-long-error/
        syncOptions:
          - ServerSideApply=true
    '''


  def __init__(self, app_name: str, env_name: str, template_vars: dict, app_viewer: ResourceViewer = None) -> None:
    self._config = get_config()

    super().__init__(app_name, env_name, template_vars, app_viewer)

  def _find_deploying_apps(self, app_deployer_name:str) -> tuple:
    for env_name, env_data in self._config.get_envs().items():
      for app_name, app_data in env_data['apps'].items():
        if 'app_deployer' in app_data and 'project' in app_data and 'destination_namespace' in app_data and \
            app_deployer_name == app_data['app_deployer']:
          yield (app_name, env_name, app_data['project'], app_data['destination_namespace'])

  def generate_resources(self) -> str:
    resources = []
    renderer = JinjaRenderer()

    for (app_name, env_name, project, destination_namespace) in self._find_deploying_apps(self.app_name):
      template_vars = merge({}, self.template_vars, {
        '__application': {
          'application_name': '-'.join([app_name, env_name]).replace('_', '-'),
          'path': os.path.join(os.path.basename(self._config.get_output_dir()), env_name, app_name),
          'project': project,
          'destination_namespace': destination_namespace
        }
      })
      content = renderer.render(textwrap.dedent(self.APPLICATION_RESOUCE_TEMPLATE), template_vars)
      resources.append(content)

    return '---'.join(resources)


class Application(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, template_vars: dict, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, template_vars, app_viewer)

  def generate_resources(self) -> str:
    resources = []
    renderer = JinjaRenderer(self.app_viewer)

    yml_children = self.app_viewer.get_files_children('.yml$')
    for yml_child in yml_children:
      resources.append(yml_child.content)

    yml_j2_children = self.app_viewer.get_files_children('.yml.j2$')
    for yml_j2_child in yml_j2_children:
      content = renderer.render(yml_j2_child.content, self.template_vars)
      resources.append(content)

    return '---'.join(resources)


class KustomizeApplication(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, template_vars: dict, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, template_vars, app_viewer)

  def _run_kustomize(self, dir_path: str) -> str:
    process = subprocess.Popen(['kubectl', 'kustomize', '--enable-helm',
                                dir_path],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                universal_newlines=True)
    stdout, stderr = process.communicate()

    if stderr:
      log.error('Kustomize error: {}'.format(stderr))
      raise Exception

    return stdout

  def generate_resources(self) -> str:
    config = get_config()
    if os.path.exists(config.get_tmp_dir()):
      shutil.rmtree(config.get_tmp_dir())

    tmp_resource_writer = ResourceWriter(config.get_tmp_dir())
    renderer = JinjaRenderer(self.app_viewer)

    yml_children = self.app_viewer.get_files_children('.yml$')
    for yml_child in yml_children:
      dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
      for resource_kind, resource_name, resource_yml in multi_resource_parser(yml_child.content):
        tmp_resource_writer.store_resource(dir_rel_path, resource_kind, resource_name, resource_yml)

    yml_j2_children = self.app_viewer.get_files_children('.yml.j2$')
    for yml_j2_child in yml_j2_children:
      content = renderer.render(yml_j2_child.content, self.template_vars)

      dir_rel_path = extract_dir_rel_path(yml_j2_child.element_rel_path)
      for resource_kind, resource_name, resource_yml in multi_resource_parser(content):
        tmp_resource_writer.store_resource(dir_rel_path, resource_kind, resource_name, resource_yml)

    tmp_resource_writer.write_resources()
    tmp_source_viewer = ResourceViewer(os.path.join(config.get_tmp_dir(), self.app_viewer.name))
    tmp_source_viewer.build()

    env_child = tmp_source_viewer.get_child(self.env_name)
    if env_child:
      yml_child = env_child.get_child('kustomization.yml')
      if yml_child:
        return self._run_kustomize(os.path.join(tmp_source_viewer.root_element_abs_path, extract_dir_rel_path(yml_child.element_rel_path)))
      else:
        log.error('Missing kustomization.yml in the overlay directory. Skipping application')
    else:
      base_child = tmp_source_viewer.get_child('base')
      if base_child:
        yml_child = base_child.get_child('kustomization.yml')
        if yml_child:
          return self._run_kustomize(os.path.join(tmp_source_viewer.root_element_abs_path, extract_dir_rel_path(yml_child.element_rel_path)))
        else:
          log.error('Missing kustomization.yml in the base directory. Skipping application')

    yml_child = tmp_source_viewer.get_child('kustomization.yml')
    if yml_child:
      return self._run_kustomize(os.path.join(tmp_source_viewer.root_element_abs_path, extract_dir_rel_path(yml_child.element_rel_path)))
    else:
      log.error('Missing kustomization.yml in the application directory. Skipping application')


def application_factory(viewer: ResourceViewer, app_name: str, env_name: str, template_vars: dict) -> AbstractApplication:
  app_child = viewer.get_child(app_name)

  if app_child:
    kustomize_children = app_child.get_files_children('kustomization.yml')

    if not kustomize_children:
      return Application(app_name, env_name, template_vars, app_child)
    else:
      return KustomizeApplication(app_name, env_name, template_vars, app_child)
  else:
    return AppOfApps(app_name, env_name, template_vars, None)

import logging
import os
from abc import ABC, abstractmethod
import subprocess
import shutil
import textwrap

from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.utils import multi_resource_parser, merge_dicts
from make_argocd_fly.config import get_config

log = logging.getLogger(__name__)


class AbstractApplication(ABC):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__()

    self.app_name = app_name
    self.env_name = env_name
    self.app_viewer = app_viewer
    self.config = get_config()

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
    {%- if argocd.finalizers | default([]) %}
      finalizers:
      {{ argocd.finalizers | to_nice_yaml | trim }}
    {%- else %}
      finalizers: []
    {%- endif %}
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
        {{ argocd.sync_policy | default({}) | to_nice_yaml(indent=2) | trim | indent(4) }}
    '''

  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    self._config = get_config()
    super().__init__(app_name, env_name, app_viewer)

    log.debug('Created application {} of type {} for environment {}'.format(app_name, __class__.__name__, env_name))

  def _find_deploying_apps(self, app_deployer_name:str, app_deployer_env_name: str) -> tuple:
    for env_name, env_data in self._config.get_envs().items():
      for app_name, app_data in env_data['apps'].items():
        if 'app_deployer' in app_data and 'project' in app_data and 'destination_namespace' in app_data:
          if app_deployer_name == app_data['app_deployer'] and (('app_deployer_env' not in app_data and env_name == app_deployer_env_name) or \
              ('app_deployer_env' in app_data and app_deployer_env_name == app_data['app_deployer_env'])):
            yield (app_name, env_name, app_data['project'], app_data['destination_namespace'])

  def generate_resources(self) -> str:
    log.debug('Generating resources for application {} in environment {}'.format(self.app_name, self.env_name))

    resources = []
    renderer = JinjaRenderer()

    for (app_name, env_name, project, destination_namespace) in self._find_deploying_apps(self.app_name, self.env_name):
      template_vars = merge_dicts(self.config.get_vars(), self.config.get_env_vars(env_name), self.config.get_app_vars(env_name, app_name), {
        '__application': {
          'application_name': '-'.join([os.path.basename(app_name), env_name]).replace('_', '-'),
          'path': os.path.join(os.path.basename(self._config.get_output_dir()), env_name, app_name),
          'project': project,
          'destination_namespace': destination_namespace
        }
      })
      content = renderer.render(textwrap.dedent(self.APPLICATION_RESOUCE_TEMPLATE), template_vars)
      resources.append(content)

    return '\n---\n'.join(resources)


class Application(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, app_viewer)

    log.debug('Created application {} of type {} for environment {}'.format(app_name, __class__.__name__, env_name))

  def generate_resources(self) -> str:
    log.debug('Generating resources for application {} in environment {}'.format(self.app_name, self.env_name))

    resources = []
    renderer = JinjaRenderer(self.app_viewer)

    yml_children = self.app_viewer.get_files_children('(\.yml|\.yml\.j2)$')
    for yml_child in yml_children:
      content = yml_child.content
      if yml_child.element_rel_path.endswith('.j2'):
        template_vars = merge_dicts({}, self.config.get_vars(), self.config.get_env_vars(self.env_name), self.config.get_app_vars(self.env_name, self.app_name))
        content = renderer.render(content, template_vars, yml_child.element_rel_path)

      resources.append(content)

    return '\n---\n'.join(resources)


class KustomizeApplication(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, app_viewer)

    log.debug('Created application {} of type {} for environment {}'.format(app_name, __class__.__name__, env_name))

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

  def _prepare_kustomization_directory(self) -> str:
    config = get_config()
    tmp_dir = config.get_tmp_dir()

    if os.path.exists(tmp_dir):
      shutil.rmtree(tmp_dir)

    tmp_resource_writer = ResourceWriter(tmp_dir)
    renderer = JinjaRenderer(self.app_viewer)

    yml_children = self.app_viewer.get_files_children('(\.yml|\.yml\.j2)$', ['base', self.env_name])
    for yml_child in yml_children:
      content = yml_child.content
      if yml_child.element_rel_path.endswith('.j2'):
        template_vars = merge_dicts({}, self.config.get_vars(), self.config.get_env_vars(self.env_name), self.config.get_app_vars(self.env_name, self.app_name))
        content = renderer.render(content, template_vars, yml_child.element_rel_path)

      dir_rel_path = os.path.dirname(yml_child.element_rel_path)
      for resource_kind, resource_name, resource_yml in multi_resource_parser(content):
        tmp_resource_writer.store_resource(self.env_name, dir_rel_path, resource_kind, resource_name, resource_yml)

    tmp_resource_writer.write_resources()

    return os.path.join(tmp_dir, self.app_viewer.element_rel_path)

  def generate_resources(self) -> str:
    log.debug('Generating resources for application {} in environment {}'.format(self.app_name, self.env_name))

    tmp_source_viewer = ResourceViewer(self._prepare_kustomization_directory())
    tmp_source_viewer.build()

    yml_child = tmp_source_viewer.get_element(os.path.join(self.env_name, 'kustomization.yml'))
    if yml_child:
      return self._run_kustomize(os.path.join(tmp_source_viewer.root_element_abs_path, os.path.dirname(yml_child.element_rel_path)))

    yml_child = tmp_source_viewer.get_element(os.path.join('base', 'kustomization.yml'))
    if yml_child:
      return self._run_kustomize(os.path.join(tmp_source_viewer.root_element_abs_path, os.path.dirname(yml_child.element_rel_path)))

    yml_child = tmp_source_viewer.get_element('kustomization.yml')
    if yml_child:
      return self._run_kustomize(os.path.join(tmp_source_viewer.root_element_abs_path, os.path.dirname(yml_child.element_rel_path)))

    log.error('Missing kustomization.yml in the application directory. Skipping application')
    return ''


def application_factory(app_viewer: ResourceViewer, app_name: str, env_name: str) -> AbstractApplication:
  if app_viewer:
    kustomize_children = app_viewer.get_files_children('kustomization.yml')

    if not kustomize_children:
      return Application(app_name, env_name, app_viewer)
    else:
      return KustomizeApplication(app_name, env_name, app_viewer)
  else:
    return AppOfApps(app_name, env_name, None)

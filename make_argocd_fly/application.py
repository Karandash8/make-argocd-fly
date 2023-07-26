import logging
import os
from abc import ABC, abstractmethod
import subprocess
import shutil

from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.utils import extract_dir_rel_path, multi_resource_parser
from make_argocd_fly.config import get_config

log = logging.getLogger(__name__)


APPLICATION_RESOUCE_TEMPLATE = \
'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{ _application_name }}
  namespace: {{ _argocd_namespace }}
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: {{ _project }}
  source:
    repoURL: {{ _repo_url }}
    targetRevision: {{ _target_revision }}
    path: {{ _path }}
  destination:
    server: {{ _api_server }}
    namespace: {{ _destination_namespace }}
  syncPolicy:
    automated:
      selfHeal: true
      prune: true
      allowEmpty: true
    # https://www.arthurkoziel.com/fixing-argocd-crd-too-long-error/
    syncOptions:
      - ServerSideApply=true
'''


def generate_application_resource(template_vars: dict) -> str:
    renderer = JinjaRenderer()
    return renderer.render(APPLICATION_RESOUCE_TEMPLATE, template_vars)


class AbstractApplication(ABC):
  def __init__(self, app_viewer: ResourceViewer, env_name: str, template_vars: dict) -> None:
    super().__init__()

    self.app_viewer = app_viewer
    self.env_name = env_name
    self.template_vars = template_vars
    self.name = app_viewer.name

  @abstractmethod
  def generate_resources(self) -> None:
    pass


class Application(AbstractApplication):
  def __init__(self, app_viewer: ResourceViewer, env_name: str, template_vars: dict) -> None:
    super().__init__(app_viewer, env_name, template_vars)

  def generate_resources(self) -> None:
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
  def __init__(self, app_viewer: ResourceViewer, env_name: str, template_vars: dict) -> None:
    super().__init__(app_viewer, env_name, template_vars)

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

  def generate_resources(self) -> None:
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

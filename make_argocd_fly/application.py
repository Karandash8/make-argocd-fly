import logging
import os
from abc import ABC, abstractmethod
import textwrap
import shutil
from pprint import pformat

from make_argocd_fly.resource import ResourceViewer
from make_argocd_fly.utils import merge_dicts_with_overrides, VarsResolver, get_app_rel_path
from make_argocd_fly.config import get_config
from make_argocd_fly.cliparams import get_cli_params
from make_argocd_fly.steps import FindAppsStep, RenderYamlStep, RenderJinjaFromViewerStep, RenderJinjaFromMemoryStep, \
  WriteResourcesStep, ReadSourceStep, RunKustomizeStep
from make_argocd_fly.exceptions import ResourceViewerIsFake

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
  APPLICATION_RESOUCE_TEMPLATE = textwrap.dedent('''\
    apiVersion: argoproj.io/v1alpha1
    kind: Application
    metadata:
      name: {{ __application.application_name }}
      namespace: {{ argocd.namespace | default('argocd') }}
    {% if 'sync_wave' in argocd %}
      annotations:
        argocd.argoproj.io/sync-wave: "{{ argocd.sync_wave }}"
    {% endif %}
    {%- if argocd.finalizers | default([]) %}
      finalizers:
      {{ argocd.finalizers | to_nice_yaml | trim }}
    {%- else %}
      finalizers: []
    {%- endif %}
    spec:
      project: {{ argocd.project | default('default') }}
      source:
        repoURL: {{ argocd.source.repo_url }}
        targetRevision: {{ argocd.source.target_revision }}
        path: {{ __application.path }}
    {% if 'directory' in argocd.source and 'recurse' in argocd.source.directory %}
        directory:
          recurse: {{ argocd.source.directory.recurse }}
    {% endif %}
      destination:
        server: {{ argocd.destination.server }}
        namespace: {{ argocd.destination.namespace | default('argocd') }}
      syncPolicy:
        {{ argocd.sync_policy | default({}) | to_nice_yaml(indent=2) | trim | indent(4) }}
      {%- if argocd.ignoreDifferences | default([]) %}
      ignoreDifferences:
      {{ argocd.ignoreDifferences | default([]) | to_nice_yaml(indent=2) | trim | indent(2) }}
      {%- endif %}
    ''')

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
        '__application': {
          'application_name': '-'.join([os.path.basename(app_name), env_name]).replace('_', '-'),
          'path': os.path.join(os.path.basename(self.config.output_dir), env_name, app_name)
        },
        'env_name': env_name,
        'app_name': app_name
      }
      global_vars = self.config._get_global_vars()
      env_vars = self.config.get_env_vars(env_name)
      app_vars = self.config.get_app_vars(env_name, app_name)

      partially_resolved_global_vars = merge_dicts_with_overrides(
        extra_vars,
        VarsResolver.resolve_all(global_vars,
                                 merge_dicts_with_overrides(extra_vars, global_vars),
                                 var_identifier=self.cli_params.var_identifier,
                                 allow_unresolved=True)
      )
      partially_resolved_env_vars = merge_dicts_with_overrides(
        partially_resolved_global_vars,
        VarsResolver.resolve_all(env_vars,
                                 merge_dicts_with_overrides(partially_resolved_global_vars, env_vars),
                                 var_identifier=self.cli_params.var_identifier,
                                 allow_unresolved=True)
      )
      partially_resolved_app_vars = merge_dicts_with_overrides(
        partially_resolved_env_vars,
        VarsResolver.resolve_all(app_vars,
                                 merge_dicts_with_overrides(partially_resolved_env_vars, app_vars),
                                 var_identifier=self.cli_params.var_identifier,
                                 allow_unresolved=True)
      )
      resolved_vars = VarsResolver.resolve_all(partially_resolved_app_vars,
                                               partially_resolved_app_vars,
                                               var_identifier=self.cli_params.var_identifier,
                                               allow_unresolved=False)

      if self.cli_params.print_vars:
        log.info(f'Variables for application {self.app_name} in environment {self.env_name}:\n{pformat(resolved_vars)}')

      self.render_jinja_step.configure(self.env_name, self.app_name, self.APPLICATION_RESOUCE_TEMPLATE, resolved_vars)
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
      'env_name': self.env_name,
      'app_name': self.app_name
    }
    global_vars = self.config._get_global_vars()
    env_vars = self.config.get_env_vars(self.env_name)
    app_vars = self.config.get_app_vars(self.env_name, self.app_name)

    partially_resolved_global_vars = merge_dicts_with_overrides(
      extra_vars,
      VarsResolver.resolve_all(global_vars,
                               merge_dicts_with_overrides(extra_vars, global_vars),
                               var_identifier=self.cli_params.var_identifier,
                               allow_unresolved=True)
    )
    partially_resolved_env_vars = merge_dicts_with_overrides(
      partially_resolved_global_vars,
      VarsResolver.resolve_all(env_vars,
                               merge_dicts_with_overrides(partially_resolved_global_vars, env_vars),
                               var_identifier=self.cli_params.var_identifier,
                               allow_unresolved=True)
    )
    partially_resolved_app_vars = merge_dicts_with_overrides(
      partially_resolved_env_vars,
      VarsResolver.resolve_all(app_vars,
                               merge_dicts_with_overrides(partially_resolved_env_vars, app_vars),
                               var_identifier=self.cli_params.var_identifier,
                               allow_unresolved=False)
    )
    resolved_vars = VarsResolver.resolve_all(partially_resolved_app_vars,
                                             partially_resolved_app_vars,
                                             var_identifier=self.cli_params.var_identifier,
                                             allow_unresolved=False)

    if self.cli_params.print_vars:
      log.info(f'Variables for application {self.app_name} in environment {self.env_name}:\n{pformat(resolved_vars)}')

    yml_children = self.app_viewer.get_files_children(r'(\.yml)$')
    self.render_yaml_step.configure(self.env_name, self.app_name, yml_children)
    await self.render_yaml_step.run()

    j2_children = self.app_viewer.get_files_children(r'(\.yml\.j2)$')
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
      'env_name': self.env_name,
      'app_name': self.app_name
    }
    global_vars = self.config._get_global_vars()
    env_vars = self.config.get_env_vars(self.env_name)
    app_vars = self.config.get_app_vars(self.env_name, self.app_name)

    partially_resolved_global_vars = merge_dicts_with_overrides(
      extra_vars,
      VarsResolver.resolve_all(global_vars,
                               merge_dicts_with_overrides(extra_vars, global_vars),
                               var_identifier=self.cli_params.var_identifier,
                               allow_unresolved=True)
    )
    partially_resolved_env_vars = merge_dicts_with_overrides(
      partially_resolved_global_vars,
      VarsResolver.resolve_all(env_vars,
                               merge_dicts_with_overrides(partially_resolved_global_vars, env_vars),
                               var_identifier=self.cli_params.var_identifier,
                               allow_unresolved=True)
    )
    partially_resolved_app_vars = merge_dicts_with_overrides(
      partially_resolved_env_vars,
      VarsResolver.resolve_all(app_vars,
                               merge_dicts_with_overrides(partially_resolved_env_vars, app_vars),
                               var_identifier=self.cli_params.var_identifier,
                               allow_unresolved=False)
    )
    resolved_vars = VarsResolver.resolve_all(partially_resolved_app_vars,
                                             partially_resolved_app_vars,
                                             var_identifier=self.cli_params.var_identifier,
                                             allow_unresolved=False)

    if self.cli_params.print_vars:
      log.info(f'Variables for application {self.app_name} in environment {self.env_name}:\n{pformat(resolved_vars)}')

    yml_children = self.app_viewer.get_files_children(r'(\.yml)$', ['base', self.env_name])
    self.render_yaml_step.configure(self.env_name, self.app_name, yml_children)
    await self.render_yaml_step.run()

    j2_children = self.app_viewer.get_files_children(r'(\.yml\.j2)$', ['base', self.env_name])
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
    kustomize_children = viewer.get_files_children('kustomization.yml')

    if kustomize_children:
      return KustomizeApplication(app_name, env_name, viewer)
    else:
      return SimpleApplication(app_name, env_name, viewer)
  except ResourceViewerIsFake:
    return AppOfAppsApplication(app_name, env_name, viewer)

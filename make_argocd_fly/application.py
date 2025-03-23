import logging
import os
from abc import ABC, abstractmethod
import textwrap
import shutil
from pprint import pformat

from make_argocd_fly.resource import ResourceViewer
from make_argocd_fly.utils import merge_dicts, VarsResolver, get_app_rel_path
from make_argocd_fly.config import get_config
from make_argocd_fly.params import get_params
from make_argocd_fly.steps import FindAppsStep, RenderYamlStep, RenderJinjaFromViewerStep, RenderJinjaFromMemoryStep, \
  WriteResourcesStep, ReadSourceStep, RunKustomizeStep
from make_argocd_fly.exceptions import MissingApplicationDirectoryError

log = logging.getLogger(__name__)


class AbstractApplication(ABC):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__()

    self.app_name = app_name
    self.env_name = env_name
    self.app_viewer = app_viewer
    self.config = get_config()
    self.params = get_params()

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

  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.find_apps_step = FindAppsStep()
    self.render_jinja_step = RenderJinjaFromMemoryStep()
    self.write_resources_step = WriteResourcesStep()

    log.debug('Created application {} with {} for environment {}'.format(app_name, __class__.__name__, env_name))

  async def process(self) -> None:
    log.debug('Starting to process application {} in environment {}'.format(self.app_name, self.env_name))

    self.find_apps_step.configure(self.env_name, self.app_name)
    await self.find_apps_step.run()

    for (app_name, env_name) in self.find_apps_step.get_apps():
      global_vars = merge_dicts(self.config.get_global_vars(),
                                {
                                  '__application': {
                                    'application_name': '-'.join([os.path.basename(app_name), env_name]).replace('_', '-'),
                                    'path': os.path.join(os.path.basename(self.config.output_dir), env_name, app_name)
                                  },
                                  'env_name': env_name,
                                  'app_name': app_name
                                })
      global_vars_resolved = VarsResolver.resolve_all(global_vars,
                                                      global_vars,
                                                      var_identifier=self.params.var_identifier)
      env_vars_resolved = merge_dicts(global_vars_resolved,
                                      VarsResolver.resolve_all(self.config.get_env_vars(env_name),
                                                               merge_dicts(global_vars_resolved, self.config.get_env_vars(self.env_name)),
                                                               var_identifier=self.params.var_identifier))
      template_vars = merge_dicts(env_vars_resolved,
                                  VarsResolver.resolve_all(self.config.get_app_vars(env_name, app_name),
                                                           merge_dicts(env_vars_resolved, self.config.get_app_vars(env_name, app_name)),
                                                           var_identifier=self.params.var_identifier))

      self.render_jinja_step.configure(self.env_name, self.app_name, self.APPLICATION_RESOUCE_TEMPLATE, template_vars)
      await self.render_jinja_step.run()

    log.debug('Generated resources for application {} in environment {}'.format(self.app_name, self.env_name))

    # Clean up output directory for the application
    app_output_dir = os.path.join(self.config.output_dir, get_app_rel_path(self.env_name, self.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    self.write_resources_step.configure(self.config.output_dir, self.render_jinja_step.get_resources())
    await self.write_resources_step.run()
    log.info('Updated application {} in environment {}'.format(self.app_name, self.env_name))


class SimpleApplication(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.render_yaml_step = RenderYamlStep()
    self.render_jinja_step = RenderJinjaFromViewerStep(app_viewer)
    self.write_resources_step = WriteResourcesStep()

    log.debug('Created application {} with {} for environment {}'.format(app_name, __class__.__name__, env_name))

  async def process(self) -> None:
    log.debug('Starting to process application {} in environment {}'.format(self.app_name, self.env_name))

    global_vars = merge_dicts(self.config.get_global_vars(),
                              {
                                'env_name': self.env_name,
                                'app_name': self.app_name
                              })
    global_vars_resolved = VarsResolver.resolve_all(global_vars,
                                                    global_vars,
                                                    var_identifier=self.params.var_identifier)
    env_vars_resolved = merge_dicts(global_vars_resolved,
                                    VarsResolver.resolve_all(self.config.get_env_vars(self.env_name),
                                                             merge_dicts(global_vars_resolved, self.config.get_env_vars(self.env_name)),
                                                             var_identifier=self.params.var_identifier))
    template_vars = merge_dicts(env_vars_resolved,
                                VarsResolver.resolve_all(self.config.get_app_vars(self.env_name, self.app_name),
                                                         merge_dicts(env_vars_resolved, self.config.get_app_vars(self.env_name, self.app_name)),
                                                         var_identifier=self.params.var_identifier))

    if self.params.print_vars:
      log.info('Variables for application {} in environment {}:\n{}'.format(self.app_name, self.env_name, pformat(template_vars)))

    yml_children = self.app_viewer.get_files_children(r'(\.yml)$')
    self.render_yaml_step.configure(self.env_name, self.app_name, yml_children)
    await self.render_yaml_step.run()

    j2_children = self.app_viewer.get_files_children(r'(\.yml\.j2)$')
    self.render_jinja_step.configure(self.env_name, self.app_name, j2_children, template_vars)
    await self.render_jinja_step.run()

    log.debug('Generated resources for application {} in environment {}'.format(self.app_name, self.env_name))

    # Clean up output directory for the application
    app_output_dir = os.path.join(self.config.output_dir, get_app_rel_path(self.env_name, self.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    self.write_resources_step.configure(self.config.output_dir, self.render_yaml_step.get_resources() + self.render_jinja_step.get_resources())
    await self.write_resources_step.run()

    log.info('Updated application {} in environment {}'.format(self.app_name, self.env_name))


class KustomizeApplication(AbstractApplication):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.render_yaml_step = RenderYamlStep()
    self.render_jinja_step = RenderJinjaFromViewerStep(app_viewer)
    self.tmp_write_resources_step = WriteResourcesStep()
    self.tmp_read_source_step = ReadSourceStep()
    self.run_kustomize_step = RunKustomizeStep()
    self.write_resources_step = WriteResourcesStep()

    log.debug('Created application {} with {} for environment {}'.format(app_name, __class__.__name__, env_name))

  async def process(self) -> None:
    log.debug('Starting to process application {} in environment {}'.format(self.app_name, self.env_name))

    global_vars = merge_dicts(self.config.get_global_vars(),
                              {
                                'env_name': self.env_name,
                                'app_name': self.app_name
                              })
    global_vars_resolved = VarsResolver.resolve_all(global_vars,
                                                    global_vars,
                                                    var_identifier=self.params.var_identifier)
    env_vars_resolved = merge_dicts(global_vars_resolved,
                                    VarsResolver.resolve_all(self.config.get_env_vars(self.env_name),
                                                             merge_dicts(global_vars_resolved, self.config.get_env_vars(self.env_name)),
                                                             var_identifier=self.params.var_identifier))
    template_vars = merge_dicts(env_vars_resolved,
                                VarsResolver.resolve_all(self.config.get_app_vars(self.env_name, self.app_name),
                                                         merge_dicts(env_vars_resolved, self.config.get_app_vars(self.env_name, self.app_name)),
                                                         var_identifier=self.params.var_identifier))

    if self.params.print_vars:
      log.info('Variables for application {} in environment {}:\n{}'.format(self.app_name, self.env_name, pformat(template_vars)))

    yml_children = self.app_viewer.get_files_children(r'(\.yml)$', ['base', self.env_name])
    self.render_yaml_step.configure(self.env_name, self.app_name, yml_children)
    await self.render_yaml_step.run()

    j2_children = self.app_viewer.get_files_children(r'(\.yml\.j2)$', ['base', self.env_name])
    self.render_jinja_step.configure(self.env_name, self.app_name, j2_children, template_vars)
    await self.render_jinja_step.run()

    self.tmp_write_resources_step.configure(self.config.tmp_dir, self.render_yaml_step.get_resources() + self.render_jinja_step.get_resources())
    await self.tmp_write_resources_step.run()

    self.tmp_read_source_step.configure(os.path.join(self.config.tmp_dir, get_app_rel_path(self.env_name, self.app_name)))
    await self.tmp_read_source_step.run()

    self.run_kustomize_step.configure(self.env_name, self.app_name, self.tmp_read_source_step.get_viewer())
    await self.run_kustomize_step.run()

    log.debug('Generated resources for application {} in environment {}'.format(self.app_name, self.env_name))

    # Clean up output directory for the application
    app_output_dir = os.path.join(self.config.output_dir, get_app_rel_path(self.env_name, self.app_name))
    if os.path.exists(app_output_dir):
      shutil.rmtree(app_output_dir)

    self.write_resources_step.configure(self.config.output_dir, self.run_kustomize_step.get_resources())
    await self.write_resources_step.run()

    log.info('Updated application {} in environment {}'.format(self.app_name, self.env_name))


async def application_factory(env_name: str, app_name: str, source_path: str) -> AbstractApplication:
  read_source_step = ReadSourceStep()
  read_source_step.configure(source_path)

  try:
    await read_source_step.run()
    viewer = read_source_step.get_viewer()

    kustomize_children = viewer.get_files_children('kustomization.yml')

    if kustomize_children:
      return KustomizeApplication(app_name, env_name, viewer)
    else:
      return SimpleApplication(app_name, env_name, viewer)
  except MissingApplicationDirectoryError:
    return AppOfAppsApplication(app_name, env_name)

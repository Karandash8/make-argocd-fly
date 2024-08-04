import logging
import os
from abc import ABC, abstractmethod
import textwrap
from pprint import pformat

from make_argocd_fly.resource import ResourceViewer
from make_argocd_fly.utils import merge_dicts, VarsResolver, get_app_rel_path
from make_argocd_fly.config import get_config
from make_argocd_fly.cli_args import get_cli_args
from make_argocd_fly.steps import FindAppsStep, RenderYamlStep, RenderJinjaFromViewerStep, RenderJinjaFromMemoryStep, \
  WriteResourcesStep, ReadSourceStep, RunKustomizeStep
from make_argocd_fly.exceptions import MissingSourceResourcesError

log = logging.getLogger(__name__)


class AbstractWorkflow(ABC):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__()

    self.app_name = app_name
    self.env_name = env_name
    self.app_viewer = app_viewer
    self.config = get_config()
    self.cli_args = get_cli_args()

  @abstractmethod
  async def process(self) -> None:
    pass


class AppOfAppsWorkflow(AbstractWorkflow):
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
      {%- if argocd.ignoreDifferences | default([]) %}
      ignoreDifferences:
      {{ argocd.ignoreDifferences | default([]) | to_nice_yaml(indent=2) | trim | indent(2) }}
      {%- endif %}
    '''

  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.find_apps_step = FindAppsStep()
    self.render_jinja_step = RenderJinjaFromMemoryStep()
    self.write_resources_step = WriteResourcesStep()

    log.debug('Created application {} with {} for environment {}'.format(app_name, __class__.__name__, env_name))

  async def process(self) -> None:
    log.debug('Starting to process application {} in environment {}'.format(self.app_name, self.env_name))

    self.find_apps_step.configure(self.app_name, self.env_name)
    await self.find_apps_step.run()

    for (app_name, env_name, project, destination_namespace) in self.find_apps_step.get_apps():
      template_vars = VarsResolver.resolve_all(merge_dicts(self.config.get_vars(), self.config.get_env_vars(env_name),
                                                           self.config.get_app_vars(env_name, app_name), {
                                                           '__application': {
                                                             'application_name': '-'.join([os.path.basename(app_name), env_name]).replace('_', '-'),
                                                             'path': os.path.join(os.path.basename(self.config.get_output_dir()),
                                                                                  env_name, app_name
                                                                                  ),
                                                             'project': project,
                                                             'destination_namespace': destination_namespace
                                                           },
                                                           'env_name': env_name,
                                                           'app_name': app_name}),
                                               var_identifier=self.cli_args.get_var_identifier())

      self.render_jinja_step.configure(textwrap.dedent(self.APPLICATION_RESOUCE_TEMPLATE), self.app_name, self.env_name, template_vars)
      await self.render_jinja_step.run()

    log.debug('Generated resources for application {} in environment {}'.format(self.app_name, self.env_name))

    self.write_resources_step.configure(self.config.get_output_dir(), self.render_jinja_step.get_resources())
    await self.write_resources_step.run()
    log.info('Updated application {} in environment {}'.format(self.app_name, self.env_name))


class SimpleWorkflow(AbstractWorkflow):
  def __init__(self, app_name: str, env_name: str, app_viewer: ResourceViewer = None) -> None:
    super().__init__(app_name, env_name, app_viewer)
    self.render_yaml_step = RenderYamlStep()
    self.render_jinja_step = RenderJinjaFromViewerStep(app_viewer)
    self.write_resources_step = WriteResourcesStep()

    log.debug('Created application {} with {} for environment {}'.format(app_name, __class__.__name__, env_name))

  async def process(self) -> None:
    log.debug('Starting to process application {} in environment {}'.format(self.app_name, self.env_name))

    template_vars = VarsResolver.resolve_all(merge_dicts(self.config.get_vars(), self.config.get_env_vars(self.env_name),
                                                         self.config.get_app_vars(self.env_name, self.app_name),
                                                         {'env_name': self.env_name, 'app_name': self.app_name}),
                                             var_identifier=self.cli_args.get_var_identifier())
    if self.cli_args.get_print_vars():
      log.info('Variables for application {} in environment {}:\n{}'.format(self.app_name, self.env_name, pformat(template_vars)))

    yml_children = self.app_viewer.get_files_children(r'(\.yml)$')
    self.render_yaml_step.configure(yml_children, self.app_name, self.env_name)
    await self.render_yaml_step.run()

    j2_children = self.app_viewer.get_files_children(r'(\.yml\.j2)$')
    self.render_jinja_step.configure(j2_children, self.app_name, self.env_name, template_vars)
    await self.render_jinja_step.run()

    log.debug('Generated resources for application {} in environment {}'.format(self.app_name, self.env_name))

    self.write_resources_step.configure(self.config.get_output_dir(), self.render_yaml_step.get_resources() + self.render_jinja_step.get_resources())
    await self.write_resources_step.run()

    log.info('Updated application {} in environment {}'.format(self.app_name, self.env_name))


class KustomizeWorkflow(AbstractWorkflow):
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

    template_vars = VarsResolver.resolve_all(merge_dicts(self.config.get_vars(), self.config.get_env_vars(self.env_name),
                                                         self.config.get_app_vars(self.env_name, self.app_name),
                                                         {'env_name': self.env_name, 'app_name': self.app_name}),
                                             var_identifier=self.cli_args.get_var_identifier()
                                             )
    if self.cli_args.get_print_vars():
      log.info('Variables for application {} in environment {}:\n{}'.format(self.app_name, self.env_name, pformat(template_vars)))

    yml_children = self.app_viewer.get_files_children(r'(\.yml)$', ['base', self.env_name])
    self.render_yaml_step.configure(yml_children, self.app_name, self.env_name)
    await self.render_yaml_step.run()

    j2_children = self.app_viewer.get_files_children(r'(\.yml\.j2)$', ['base', self.env_name])
    self.render_jinja_step.configure(j2_children, self.app_name, self.env_name, template_vars)
    await self.render_jinja_step.run()

    self.tmp_write_resources_step.configure(self.config.get_tmp_dir(), self.render_yaml_step.get_resources() + self.render_jinja_step.get_resources())
    await self.tmp_write_resources_step.run()

    self.tmp_read_source_step.configure(os.path.join(self.config.get_tmp_dir(), get_app_rel_path(self.app_name, self.env_name)))
    await self.tmp_read_source_step.run()

    self.run_kustomize_step.configure(self.tmp_read_source_step.get_viewer(), self.app_name, self.env_name)
    await self.run_kustomize_step.run()

    log.debug('Generated resources for application {} in environment {}'.format(self.app_name, self.env_name))

    self.write_resources_step.configure(self.config.get_output_dir(), self.run_kustomize_step.get_resources())
    await self.write_resources_step.run()

    log.info('Updated application {} in environment {}'.format(self.app_name, self.env_name))


async def workflow_factory(app_name: str, env_name: str, source_path: str) -> AbstractWorkflow:
  read_source_step = ReadSourceStep()
  read_source_step.configure(source_path)

  try:
    await read_source_step.run()
    viewer = read_source_step.get_viewer()

    kustomize_children = viewer.get_files_children('kustomization.yml')

    if not kustomize_children:
      return SimpleWorkflow(app_name, env_name, viewer)
    else:
      return KustomizeWorkflow(app_name, env_name, viewer)
  except MissingSourceResourcesError:
    return AppOfAppsWorkflow(app_name, env_name)


class Application():
  def __init__(self, app_name: str, env_name: str, workflow: AbstractWorkflow) -> None:
    self.app_name = app_name
    self.env_name = env_name
    self.workflow = workflow

  async def process(self) -> None:
    await self.workflow.process()

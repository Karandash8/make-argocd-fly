import logging
import logging.config
import yaml
import os
import argparse
import shutil

from mergedeep import merge

from make_argocd_fly.config import read_config, get_config
from make_argocd_fly.utils import multi_resource_parser
from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.application import Application, KustomizeApplication, generate_application_resource

LOG_CONFIG_FILE = 'log_config.yml'
CONFIG_FILE = 'config.yml'

try:
  with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), LOG_CONFIG_FILE)) as f:
    yaml_config = yaml.safe_load(f.read())
    logging.config.dictConfig(yaml_config)
except FileNotFoundError:
  logging.basicConfig(level='DEBUG')

log = logging.getLogger(__name__)


def find_app_in_envs(target_app_name: str, envs: dict) -> str:
  for env_name, env_data in envs.items():
    if target_app_name in env_data['apps'].keys():
      return env_name

# TODO: rework this nonsense
def run(viewer: ResourceViewer, writer: ResourceWriter) -> None:
  config = get_config()
  apps = []

  for env_name, env_data in config.get_envs().items():
    template_vars = merge({}, config.get_vars(), env_data['vars'] if 'vars' in env_data else {})

    for app_name in env_data['apps'].keys():
      app_child = viewer.get_child(app_name)
      if not app_child:
        continue

      kustomize_children = app_child.get_files_children('kustomization.yml')
      if not kustomize_children:
        apps.append(Application(app_child, env_name, template_vars))
      else:
        apps.append(KustomizeApplication(app_child, env_name, template_vars))

  for app in apps:
    for resource_kind, resource_name, resource_yml in multi_resource_parser(app.generate_resources()):
      writer.store_resource(os.path.join(app.env_name, app.name), resource_kind, resource_name, resource_yml)

  # generate Application resources
  for env_name, env_data in config.get_envs().items():
    for app_name, app_data in env_data['apps'].items():
      if app_data:
        template_vars = config.get_vars()
        full_app_name = '-'.join([app_name, env_name]).replace('_', '-')
        template_vars['_application_name'] = full_app_name
        template_vars['_argocd_namespace'] = env_data['params']['argocd_namespace']
        template_vars['_project'] = app_data['project']
        template_vars['_repo_url'] = env_data['params']['repo_url']
        template_vars['_target_revision'] = env_data['params']['target_revision']
        template_vars['_path'] = os.path.join(os.path.basename(config.get_output_dir()), env_name, app_name)
        template_vars['_api_server'] = env_data['params']['api_server']
        template_vars['_destination_namespace'] = app_data['destination_namespace']

        content = generate_application_resource(template_vars)

        app_deployer_env = find_app_in_envs(app_data['app_deployer'], config.get_envs())
        writer.store_resource(os.path.join(app_deployer_env, app_data['app_deployer']), 'Application', full_app_name, content)

def main() -> None:
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--root-dir', type=str, default=os.getcwd(), help='Root directory')
  parser.add_argument('--config-file', type=str, default=CONFIG_FILE, help='Configuration file')
  args = parser.parse_args()

  log.debug('Root directory path: {}'.format(args.root_dir))

  config = read_config(args.root_dir, args.config_file)
  source_viewer = ResourceViewer(config.get_source_dir())
  source_viewer.build()

  output_writer = ResourceWriter(config.get_output_dir())

  run(source_viewer, output_writer)

  if os.path.exists(config.get_output_dir()):
    shutil.rmtree(config.get_output_dir())
  output_writer.write_resources()

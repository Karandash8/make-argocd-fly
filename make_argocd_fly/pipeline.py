import logging
import logging.config
import yaml
import os
import argparse
import subprocess
import shutil

from make_argocd_fly.config import read_config, Config
from make_argocd_fly.utils import extract_dir_rel_path, multi_resource_parser, resource_parser
from make_argocd_fly.resource import build_resource_viewer, build_resource_writer, ResourceViewer, ResourceWriter
from make_argocd_fly.application import generate_application

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
def run(viewer: ResourceViewer, writer: ResourceWriter, config: Config) -> None:
  # write apps in a tmp dir and run kustomize
  for env_name, env_data in config.envs.items():
    if os.path.exists(config.config['tmp_dir']):
      shutil.rmtree(config.config['tmp_dir'])
    tmp_writer = build_resource_writer(config.config['tmp_dir'], None)

    for app_name in env_data['apps'].keys():
      app = viewer.get_child(app_name)
      if not app:
        continue

      yml_children = app.get_files_children('.yml$')
      for yml_child in yml_children:
        dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
        for resource_kind, resource_name, resource_yml in multi_resource_parser(yml_child.content):
          tmp_writer.store_resource(dir_rel_path, resource_kind, resource_name, resource_yml)
      tmp_writer.write_resources()

      env_child = app.get_child(env_name)
      if env_child:
        yml_child = env_child.get_child('kustomization.yml')
        if yml_child:
          dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
          process = subprocess.Popen(['kubectl', 'kustomize',
                                      os.path.join(viewer.tmp_dir_abs_path, dir_rel_path)],
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      universal_newlines=True)
          stdout, _ = process.communicate()

          for resource_kind, resource_name, resource_yml in multi_resource_parser(stdout):
            writer.store_resource(os.path.join(env_name, app.name), resource_kind, resource_name, resource_yml)
          log.debug(stdout)
      else:
        yml_child = app.get_child('kustomization.yml')
        if yml_child:
          dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
          process = subprocess.Popen(['kubectl', 'kustomize',
                                      os.path.join(viewer.tmp_dir_abs_path, dir_rel_path)],
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      universal_newlines=True)
          stdout, _ = process.communicate()

          for resource_kind, resource_name, resource_yml in multi_resource_parser(stdout):
            writer.store_resource(os.path.join(env_name, app.name), resource_kind, resource_name, resource_yml)
          log.debug(stdout)
        else:
          yml_children = app.get_files_children('.yml$')

          for yml_child in yml_children:
            dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
            for resource_kind, resource_name, resource_yml in multi_resource_parser(yml_child.content):
              writer.store_resource(os.path.join(env_name, app.name), resource_kind, resource_name, resource_yml)

  # generate Application resources
  for env_name, env_data in config.envs.items():
    for app_name, app_data in env_data['apps'].items():
      if app_data:
        template_vars = config.vars
        full_app_name = '-'.join([app_name, env_name]).replace('_', '-')
        template_vars['_application_name'] = full_app_name
        template_vars['_argocd_namespace'] = env_data['params']['argocd_namespace']
        template_vars['_project'] = app_data['project']
        template_vars['_repo_url'] = env_data['params']['repo_url']
        template_vars['_target_revision'] = env_data['params']['target_revision']
        template_vars['_path'] = os.path.join(os.path.basename(config.config['output_dir']), env_name, app_name)
        template_vars['_api_server'] = env_data['params']['api_server']
        template_vars['_destination_namespace'] = app_data['destination_namespace']

        content = generate_application(template_vars)

        app_deployer_env = find_app_in_envs(app_data['app_deployer'], config.envs)
        writer.store_resource(os.path.join(app_deployer_env, app_data['app_deployer']), 'Application', full_app_name, content)

def main() -> None:
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--env', type=str, default=None, help='Environment to render')
  parser.add_argument('--app', type=str, default=None, help='Application to render')
  parser.add_argument('--root-dir', type=str, default=os.getcwd(), help='Root directory')
  parser.add_argument('--config-file', type=str, default=CONFIG_FILE, help='Configuration file')
  args = parser.parse_args()

  root_dir = args.root_dir
  log.debug('Root directory path: {}'.format(root_dir))

  config = read_config(root_dir, args.config_file)
  source_viewer = build_resource_viewer(config.config['source_dir'], config.config['tmp_dir'], config.vars, args.app)
  output_writer = build_resource_writer(config.config['output_dir'], args.env)

  run(source_viewer, output_writer, config)

  if os.path.exists(config.config['output_dir']):
    shutil.rmtree(config.config['output_dir'])
  output_writer.write_resources()

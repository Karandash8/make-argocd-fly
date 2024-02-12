import logging
import logging.config
import yaml
import os
import argparse
import shutil

from make_argocd_fly.config import read_config
from make_argocd_fly.utils import multi_resource_parser
from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.application import application_factory

LOG_CONFIG_FILE = 'log_config.yml'
CONFIG_FILE = 'config.yml'

try:
  with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), LOG_CONFIG_FILE)) as f:
    yaml_config = yaml.safe_load(f.read())
    logging.config.dictConfig(yaml_config)
except FileNotFoundError:
  logging.basicConfig(level='DEBUG')

log = logging.getLogger(__name__)


def main() -> None:
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--root-dir', type=str, default=os.getcwd(), help='Root directory')
  parser.add_argument('--config-file', type=str, default=CONFIG_FILE, help='Configuration file')
  parser.add_argument('--render-apps', type=str, default='', help='Comma separate list of applications to render')
  parser.add_argument('--render-envs', type=str, default='', help='Comma separate list of environments to render')
  parser.add_argument('--preserve-tmp-dir', action="store_true", help='Preserve temporary directory')
  args = parser.parse_args()

  log.debug('Root directory path: {}'.format(args.root_dir))
  config = read_config(args.root_dir, args.config_file)

  log.info('Reading source directory')
  source_viewer = ResourceViewer(config.get_source_dir())
  source_viewer.build()

  tmp_dir = config.get_tmp_dir()
  if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

  apps_to_render = args.render_apps.split(',') if args.render_apps else []
  envs_to_render = args.render_envs.split(',') if args.render_envs else []
  apps = []

  log.info('Creating applications')
  for env_name, env_data in config.get_envs().items():
    if envs_to_render and env_name not in envs_to_render:
      continue

    for app_name in env_data['apps'].keys():
      if apps_to_render and app_name not in apps_to_render:
        continue

      app_viewer = source_viewer.get_element(app_name)
      apps.append(application_factory(app_viewer, app_name, env_name))

  output_writer = ResourceWriter(config.get_output_dir())

  log.info('Rendering resources')
  for app in apps:
    for resource_kind, resource_name, resource_yml in multi_resource_parser(app.generate_resources()):
      output_writer.store_resource(app.env_name, app.get_app_rel_path(), resource_kind, resource_name, resource_yml)

  log.info('Writing resources files')
  if os.path.exists(config.get_output_dir()):
    shutil.rmtree(config.get_output_dir())
  output_writer.write_resources()

  if not args.preserve_tmp_dir and os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

import logging
import logging.config
import os
import argparse
import shutil
import asyncio
import subprocess
import yaml
import yamllint

from make_argocd_fly.config import read_config, get_config
from make_argocd_fly.utils import multi_resource_parser, generate_filename
from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.application import application_factory

LOG_CONFIG_FILE = 'log_config.yml'
CONFIG_FILE = 'config.yml'

logging.basicConfig(level='INFO')

log = logging.getLogger(__name__)


def init_logging(loglevel: str) -> None:
  try:
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), LOG_CONFIG_FILE)) as f:
      yaml_config = yaml.safe_load(f.read())
      if loglevel in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        yaml_config['loggers']['root']['level'] = loglevel
      logging.config.dictConfig(yaml_config)
  except FileNotFoundError:
    pass


def create_applications(render_apps, render_envs):
  config = get_config()

  log.debug('Reading source directory')
  source_viewer = ResourceViewer(config.get_source_dir())
  source_viewer.build()

  apps_to_render = render_apps.split(',') if render_apps is not None else []
  envs_to_render = render_envs.split(',') if render_envs is not None else []
  apps = []

  log.debug('Creating applications')
  for env_name, env_data in config.get_envs().items():
    if envs_to_render and env_name not in envs_to_render:
      continue

    for app_name in env_data['apps'].keys():
      if apps_to_render and app_name not in apps_to_render:
        continue

      app_viewer = source_viewer.get_element(app_name)
      apps.append(application_factory(app_viewer, app_name, env_name))

  return apps


async def generate(render_envs, render_apps) -> None:
  config = get_config()
  apps = create_applications(render_apps, render_envs)

  log.debug('Rendering resources')
  await asyncio.gather(*[app.generate_resources() for app in apps])

  output_writer = ResourceWriter(config.get_output_dir())
  for app in apps:
    for resource_kind, resource_name, resource_yml in multi_resource_parser(app.resources):
      file_path = os.path.join(app.get_app_rel_path(), generate_filename(resource_kind, resource_name))
      output_writer.store_resource(file_path, resource_yml)

  if apps:
    log.debug('The following applications have been updated:')
  if os.path.exists(config.get_output_dir()):
    for app in apps:
      app_dir = os.path.join(config.get_output_dir(), app.get_app_rel_path())
      log.debug('Environment: {}, Application: {}, Path: {}'.format(app.env_name, app.app_name, app_dir))
      if os.path.exists(app_dir):
        shutil.rmtree(app_dir)

  log.debug('Writing resources files')
  os.makedirs(config.get_output_dir(), exist_ok=True)
  await output_writer.write_resources()


def main() -> None:
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--root-dir', type=str, default=os.getcwd(), help='Root directory')
  parser.add_argument('--config-file', type=str, default=CONFIG_FILE, help='Configuration file')
  parser.add_argument('--render-apps', type=str, default=None, help='Comma separate list of applications to render')
  parser.add_argument('--render-envs', type=str, default=None, help='Comma separate list of environments to render')
  parser.add_argument('--skip-generate', action='store_true', help='Skip resource generation')
  parser.add_argument('--preserve-tmp-dir', action='store_true', help='Preserve temporary directory')
  parser.add_argument('--clean', action='store_true', help='Clean all applications in output directory')
  parser.add_argument('--yaml-linter', action='store_true', help='Run yamllint against output directory (https://github.com/adrienverge/yamllint)')
  parser.add_argument('--kube-linter', action='store_true', help='Run kube-linter against output directory (https://github.com/stackrox/kube-linter)')
  parser.add_argument('--loglevel', type=str, default='INFO', help='DEBUG, INFO, WARNING, ERROR, CRITICAL')
  args = parser.parse_args()

  init_logging(args.loglevel)

  log.debug('Root directory path: {}'.format(os.path.abspath(args.root_dir)))
  config = read_config(os.path.abspath(args.root_dir), args.config_file)

  tmp_dir = config.get_tmp_dir()
  if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

  if args.clean:
    log.info('Cleaning all output directory')
    if os.path.exists(config.get_output_dir()):
      shutil.rmtree(config.get_output_dir())

  if not args.skip_generate:
    asyncio.run(generate(args.render_envs, args.render_apps))

  if not args.preserve_tmp_dir and os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

  # TODO: it does not make sense to write yamls on disk and then read them again to run through linters
  if args.yaml_linter:
    log.info('Running yamllint')
    process = subprocess.Popen(['yamllint', '-d', '{extends: default, rules: {line-length: disable}}', config.get_output_dir()],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
    stdout, stderr = process.communicate()

    log.info('{} {}\n\n{}'.format(yamllint.APP_NAME, yamllint.APP_VERSION, stdout))

  if args.kube_linter:
    log.info('Running kube-linter')
    process = subprocess.Popen(['kube-linter', 'lint', config.get_output_dir()],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
    stdout, stderr = process.communicate()

    log.info(stdout)
    log.info(stderr)

import logging
import logging.config
import os
import argparse
import shutil
import asyncio
import subprocess
import yaml
import yamllint

from make_argocd_fly.cli_args import populate_cli_args, get_cli_args
from make_argocd_fly.config import read_config, get_config, LOG_CONFIG_FILE, CONFIG_FILE, \
  SOURCE_DIR, OUTPUT_DIR, TMP_DIR
from make_argocd_fly.utils import latest_version_check
from make_argocd_fly.application import workflow_factory, Application


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


async def generate() -> None:
  config = get_config()
  cli_args = get_cli_args()
  render_apps = cli_args.get_render_apps()
  render_envs = cli_args.get_render_envs()

  apps_to_render = render_apps.split(',') if render_apps is not None else []
  envs_to_render = render_envs.split(',') if render_envs is not None else []
  apps = []

  log.info('Creating applications')
  for env_name, env_data in config.get_envs().items():
    if envs_to_render and env_name not in envs_to_render:
      continue

    for app_name in env_data['apps'].keys():
      if apps_to_render and app_name not in apps_to_render:
        continue

      workflow = await workflow_factory(app_name, env_name, os.path.join(config.get_source_dir(), app_name))
      apps.append(Application(app_name, env_name, workflow))

  log.info('Processing applications')
  try:
    await asyncio.gather(*[asyncio.create_task(app.process()) for app in apps])
  except Exception:
    for task in asyncio.all_tasks():
      task.cancel()
    raise


def main() -> None:
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--root-dir', type=str, default=os.getcwd(), help='Root directory (default: current directory)')
  parser.add_argument('--config-file', type=str, default=CONFIG_FILE, help='Configuration file (default: config.yml)')
  parser.add_argument('--source-dir', type=str, default=SOURCE_DIR, help='Source files directory (default: source)')
  parser.add_argument('--output-dir', type=str, default=OUTPUT_DIR, help='Output files directory (default: output)')
  parser.add_argument('--tmp-dir', type=str, default=TMP_DIR, help='Temporary files directory (default: .tmp)')
  parser.add_argument('--render-apps', type=str, default=None, help='Comma separate list of applications to render')
  parser.add_argument('--render-envs', type=str, default=None, help='Comma separate list of environments to render')
  parser.add_argument('--skip-generate', action='store_true', help='Skip resource generation')
  parser.add_argument('--preserve-tmp-dir', action='store_true', help='Preserve temporary directory')
  parser.add_argument('--remove-output-dir', action='store_true', help='Remove output directory')
  parser.add_argument('--print-vars', action='store_true', help='Print variables for each application')
  parser.add_argument('--var-identifier', type=str, default='$', help='Variable prefix in config.yml file (default: $)')
  parser.add_argument('--skip-latest-version-check', action='store_true', help='Skip latest version check')
  parser.add_argument('--yaml-linter', action='store_true', help='Run yamllint against output directory (https://github.com/adrienverge/yamllint)')
  parser.add_argument('--kube-linter', action='store_true', help='Run kube-linter against output directory (https://github.com/stackrox/kube-linter)')
  parser.add_argument('--loglevel', type=str, default='INFO', help='DEBUG, INFO, WARNING, ERROR, CRITICAL')
  args = parser.parse_args()

  init_logging(args.loglevel)
  cli_args = populate_cli_args(**vars(args))
  if not cli_args.get_skip_latest_version_check():
    latest_version_check()
  else:
    log.warning('Skipping latest version check')
  config = read_config(args.root_dir, args.config_file, cli_args)

  tmp_dir = config.get_tmp_dir()
  if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

  if cli_args.get_remove_output_dir():
    log.info('Wiping output directory')
    if os.path.exists(config.get_output_dir()):
      shutil.rmtree(config.get_output_dir())

  if not cli_args.get_skip_generate():
    asyncio.run(generate())

  if not cli_args.get_preserve_tmp_dir() and os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

  # TODO: it does not make sense to write yamls on disk and then read them again to run through linters
  if cli_args.get_yaml_linter():
    log.info('Running yamllint')
    process = subprocess.Popen(['yamllint', '-d', '{extends: default, rules: {line-length: disable}}', config.get_output_dir()],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
    stdout, stderr = process.communicate()

    log.info('{} {}\n\n{}'.format(yamllint.APP_NAME, yamllint.APP_VERSION, stdout))

  if cli_args.get_kube_linter():
    log.info('Running kube-linter')
    process = subprocess.Popen(['kube-linter', 'lint', config.get_output_dir()],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
    stdout, stderr = process.communicate()

    log.info(stdout)
    log.info(stderr)

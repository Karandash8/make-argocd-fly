import logging
import logging.config
import os
import argparse
import shutil
import asyncio
import subprocess
import yamllint

from make_argocd_fly import consts
from make_argocd_fly.warnings import init_warnings
from make_argocd_fly.cliparams import populate_cli_params, get_cli_params
from make_argocd_fly.config import populate_config, get_config
from make_argocd_fly.utils import init_logging, latest_version_check, get_package_name, get_current_version
from make_argocd_fly.application import application_factory
from make_argocd_fly.exceptions import TemplateRenderingError, InternalError, ConfigFileError, KustomizeError


logging.basicConfig(level=consts.DEFAULT_LOGLEVEL)

log = logging.getLogger(__name__)


async def generate() -> None:
  config = get_config()
  cli_params = get_cli_params()
  render_apps = cli_params.render_apps
  render_envs = cli_params.render_envs

  apps_to_render = render_apps.split(',') if render_apps is not None else []
  envs_to_render = render_envs.split(',') if render_envs is not None else []
  apps = []

  log.info('Creating applications')
  for env_name in config.list_envs():
    if envs_to_render and env_name not in envs_to_render:
      continue

    for app_name in config.list_apps(env_name):
      if apps_to_render and app_name not in apps_to_render:
        continue

      application = await application_factory(env_name, app_name, os.path.join(config.source_dir, app_name))
      apps.append(application)

  # TODO: convert to TaskGroup
  # TODO: add throttling with asyncio.Semaphore
  log.info('Processing applications')
  try:
    await asyncio.gather(*[asyncio.create_task(app.process()) for app in apps])
  except Exception as e:
    for task in asyncio.all_tasks():
      task.cancel()
    raise e


def run_yamllint() -> None:
  if not get_cli_params().yaml_linter:
    return

  log.info('Running yamllint')
  config = get_config()
  process = subprocess.Popen(['yamllint', '-d', '{extends: default, rules: {line-length: disable}}', config.output_dir],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
  stdout, stderr = process.communicate()

  log.info(f'{yamllint.APP_NAME} {yamllint.APP_VERSION}\n\n{stdout}')


def run_kube_linter() -> None:
  if not get_cli_params().kube_linter:
    return

  log.info('Running kube-linter')
  config = get_config()
  process = subprocess.Popen(['kube-linter', 'lint', config.output_dir],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
  stdout, stderr = process.communicate()

  log.info(stdout)
  log.info(stderr)


def remove_dir(dir: str) -> None:
  if os.path.exists(dir):
    shutil.rmtree(dir)


def main(**kwargs) -> None:
  try:
    cli_params = populate_cli_params(**kwargs)
    config = populate_config(cli_params.root_dir, cli_params.config_file, cli_params.config_dir, cli_params.source_dir,
                             cli_params.output_dir, cli_params.tmp_dir)

    latest_version_check()
    remove_dir(config.tmp_dir)

    if cli_params.remove_output_dir:
      log.info('Wiping output directory')
      remove_dir(config.output_dir)

    if not cli_params.skip_generate:
      asyncio.run(generate())

    if not cli_params.preserve_tmp_dir:
      remove_dir(config.tmp_dir)

    # TODO: it does not make sense to write yamls on disk and then read them again to run through linters
    run_yamllint()
    run_kube_linter()
  except (TemplateRenderingError, KustomizeError) as e:
    log.critical(f'Error generating application {e.app_name} in environment {e.env_name}')
    exit(1)
  except InternalError:
    log.critical('Internal error')
    exit(1)
  except ConfigFileError:
    log.critical('Config file error')
    exit(1)
  except Exception as e:
    raise e


def cli_entry_point() -> None:
  parser = argparse.ArgumentParser(prog='make-argocd-fly', description='Render ArgoCD Applications.')
  parser.add_argument('--root-dir', type=str, default=consts.DEFAULT_ROOT_DIR, help='Root directory (default: current directory)')
  parser.add_argument('--config-file', type=str, default=consts.DEFAULT_CONFIG_FILE, help='Configuration file (default: config.yml) # DEPRECATED')
  parser.add_argument('--config-dir', type=str, default=consts.DEFAULT_CONFIG_DIR, help='Configuration files directory (default: config)')
  parser.add_argument('--source-dir', type=str, default=consts.DEFAULT_SOURCE_DIR, help='Source files directory (default: source)')
  parser.add_argument('--output-dir', type=str, default=consts.DEFAULT_OUTPUT_DIR, help='Output files directory (default: output)')
  parser.add_argument('--tmp-dir', type=str, default=consts.DEFAULT_TMP_DIR, help='Temporary files directory (default: .tmp)')
  parser.add_argument('--render-apps', type=str, default=None, help='Comma separate list of applications to render')
  parser.add_argument('--render-envs', type=str, default=None, help='Comma separate list of environments to render')
  parser.add_argument('--skip-generate', action='store_true', help='Skip resource generation')
  parser.add_argument('--preserve-tmp-dir', action='store_true', help='Preserve temporary directory')
  parser.add_argument('--remove-output-dir', action='store_true', help='Remove output directory')
  parser.add_argument('--print-vars', action='store_true', help='Print variables for each application')
  parser.add_argument('--var-identifier', type=str, default=consts.DEFAULT_VAR_IDENTIFIER, help='Variable prefix in configuration files (default: $)')
  parser.add_argument('--skip-latest-version-check', action='store_true', help='Skip latest version check')
  parser.add_argument('--yaml-linter', action='store_true', help='Run yamllint against output directory (https://github.com/adrienverge/yamllint)')
  parser.add_argument('--kube-linter', action='store_true', help='Run kube-linter against output directory (https://github.com/stackrox/kube-linter)')
  parser.add_argument('--loglevel', type=str, default=consts.DEFAULT_LOGLEVEL, help='DEBUG, INFO, WARNING, ERROR, CRITICAL')
  parser.add_argument('--version', action='version', version=f'{get_package_name()} {get_current_version()}', help='Show version')
  args = parser.parse_args()

  init_logging(args.loglevel)
  init_warnings()
  main(**vars(args))

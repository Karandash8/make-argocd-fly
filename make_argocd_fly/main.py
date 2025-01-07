import logging
import logging.config
import os
import argparse
import shutil
import asyncio
import subprocess
import yamllint

from make_argocd_fly import consts
from make_argocd_fly.params import populate_params, get_params
from make_argocd_fly.config import read_config, get_config
from make_argocd_fly.utils import init_logging, latest_version_check, get_package_name, get_current_version
from make_argocd_fly.application import application_factory


logging.basicConfig(level=consts.DEFAULT_LOGLEVEL)

log = logging.getLogger(__name__)


async def generate() -> None:
  config = get_config()
  params = get_params()
  render_apps = params.get_render_apps()
  render_envs = params.get_render_envs()

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

      application = await application_factory(env_name, app_name, os.path.join(config.get_source_dir(), app_name))
      apps.append(application)

  # TODO: convert to TaskGroup
  # TODO: add throttling with asyncio.Semaphore
  log.info('Processing applications')
  try:
    await asyncio.gather(*[asyncio.create_task(app.process()) for app in apps])
  except Exception:
    for task in asyncio.all_tasks():
      task.cancel()
    raise Exception


def main(**kwargs) -> None:
  populate_params(**kwargs)

  params = get_params()
  init_logging(params.get_loglevel())
  config = read_config(params.get_root_dir(), params.get_config_file(), params.get_source_dir(),
                       params.get_output_dir(), params.get_tmp_dir())

  if not params.get_skip_latest_version_check():
    latest_version_check()
  else:
    log.warning('Skipping latest version check')

  tmp_dir = config.get_tmp_dir()
  if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

  if params.get_remove_output_dir():
    log.info('Wiping output directory')
    if os.path.exists(config.get_output_dir()):
      shutil.rmtree(config.get_output_dir())

  if not params.get_skip_generate():
    asyncio.run(generate())

  if not params.get_preserve_tmp_dir() and os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)

  # TODO: it does not make sense to write yamls on disk and then read them again to run through linters
  if params.get_yaml_linter():
    log.info('Running yamllint')
    process = subprocess.Popen(['yamllint', '-d', '{extends: default, rules: {line-length: disable}}', config.get_output_dir()],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
    stdout, stderr = process.communicate()

    log.info('{} {}\n\n{}'.format(yamllint.APP_NAME, yamllint.APP_VERSION, stdout))

  if params.get_kube_linter():
    log.info('Running kube-linter')
    process = subprocess.Popen(['kube-linter', 'lint', config.get_output_dir()],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
    stdout, stderr = process.communicate()

    log.info(stdout)
    log.info(stderr)


def cli_entry_point() -> None:
  parser = argparse.ArgumentParser(prog='make-argocd-fly', description='Render ArgoCD Applications.')
  parser.add_argument('--root-dir', type=str, default=consts.DEFAULT_ROOT_DIR, help='Root directory (default: current directory)')
  parser.add_argument('--config-file', type=str, default=consts.DEFAULT_CONFIG_FILE, help='Configuration file (default: config.yml)')
  parser.add_argument('--source-dir', type=str, default=consts.DEFAULT_SOURCE_DIR, help='Source files directory (default: source)')
  parser.add_argument('--output-dir', type=str, default=consts.DEFAULT_OUTPUT_DIR, help='Output files directory (default: output)')
  parser.add_argument('--tmp-dir', type=str, default=consts.DEFAULT_TMP_DIR, help='Temporary files directory (default: .tmp)')
  parser.add_argument('--render-apps', type=str, default=None, help='Comma separate list of applications to render')
  parser.add_argument('--render-envs', type=str, default=None, help='Comma separate list of environments to render')
  parser.add_argument('--skip-generate', action='store_true', help='Skip resource generation')
  parser.add_argument('--preserve-tmp-dir', action='store_true', help='Preserve temporary directory')
  parser.add_argument('--remove-output-dir', action='store_true', help='Remove output directory')
  parser.add_argument('--print-vars', action='store_true', help='Print variables for each application')
  parser.add_argument('--var-identifier', type=str, default=consts.DEFAULT_VAR_IDENTIFIER, help='Variable prefix in config.yml file (default: $)')
  parser.add_argument('--skip-latest-version-check', action='store_true', help='Skip latest version check')
  parser.add_argument('--yaml-linter', action='store_true', help='Run yamllint against output directory (https://github.com/adrienverge/yamllint)')
  parser.add_argument('--kube-linter', action='store_true', help='Run kube-linter against output directory (https://github.com/stackrox/kube-linter)')
  parser.add_argument('--loglevel', type=str, default=consts.DEFAULT_LOGLEVEL, help='DEBUG, INFO, WARNING, ERROR, CRITICAL')
  parser.add_argument('--version', action='version', version='{} {}'.format(get_package_name(), get_current_version()), help='Show version')
  args = parser.parse_args()

  main(**vars(args))

import logging
import logging.config
import os
import argparse
import time
import shutil
import asyncio
import subprocess
import yamllint

from make_argocd_fly import default
from make_argocd_fly.warning import init_warnings
from make_argocd_fly.resource.viewer import build_scoped_viewer
from make_argocd_fly.cliparam import populate_cli_params, get_cli_params
from make_argocd_fly.config import populate_config, get_config
from make_argocd_fly.util import init_logging, latest_version_check, get_package_name, get_current_version
from make_argocd_fly.exception import (TemplateRenderingError, YamlError, InternalError, ConfigFileError, KustomizeError,
                                       PathDoesNotExistError, HelmfileError)
from make_argocd_fly.pipeline import build_pipeline
from make_argocd_fly.context import Context
from make_argocd_fly.limits import RuntimeLimits
from make_argocd_fly.stats import print_stats


logging.basicConfig(level=default.LOGLEVEL)

log = logging.getLogger(__name__)


async def run_one_app(pipeline, ctx, limits: RuntimeLimits):
  async with limits.app_sem:
    await pipeline.run(ctx)


async def generate() -> None:
  config = get_config()
  cli_params = get_cli_params()

  limits = RuntimeLimits(
    app_sem=asyncio.Semaphore(cli_params.max_concurrent_apps),
    subproc_sem=asyncio.Semaphore(cli_params.max_subproc),
    io_sem=asyncio.Semaphore(cli_params.max_io),
  )
  apps = []

  viewer = build_scoped_viewer(config.source_dir)

  log.info('Creating applications')
  for env_name in config.list_filtered_envs():
    for app_name in config.list_filtered_apps(env_name):
      ctx = Context(env_name, app_name, params=config.get_params(env_name, app_name))
      pipeline = build_pipeline(ctx, limits, viewer)

      apps.append((pipeline, ctx))

  t0 = time.perf_counter()
  try:
    async with asyncio.TaskGroup() as tg:
      for (pipeline, ctx) in apps:
        tg.create_task(run_one_app(pipeline, ctx, limits))
  except ExceptionGroup as e:
    if e.exceptions:
      raise e.exceptions[0]
    else:
      raise e
  t1 = time.perf_counter()
  wall_ms = (t1 - t0) * 1000.0

  if cli_params.stats:
    print_stats(apps, wall_ms=wall_ms)


def run_yamllint() -> None:
  if not get_cli_params().yaml_linter:
    return

  log.info('Running yamllint')
  config = get_config()
  process = subprocess.Popen(['yamllint', '-d', '{extends: default, rules: {line-length: disable}}', config.output_dir],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
  stdout, _ = process.communicate()

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


def main(**kwargs) -> None:  # noqa: C901
  try:
    cli_params = populate_cli_params(**kwargs)
    config = populate_config(cli_params.root_dir, cli_params.config_dir, cli_params.source_dir,
                             cli_params.output_dir, cli_params.tmp_dir)

    latest_version_check()
    remove_dir(config.tmp_dir)

    if cli_params.remove_output_dir:
      log.info('Wiping output directory')
      remove_dir(config.output_dir)

    if not cli_params.skip_generate:
      asyncio.run(generate())

    if not cli_params.preserve_tmp_dir and not cli_params.dump_context:
      remove_dir(config.tmp_dir)

    # TODO: it does not make sense to write yamls on disk and then read them again to run through linters
    run_yamllint()
    run_kube_linter()
  except (TemplateRenderingError, YamlError, KustomizeError, HelmfileError) as e:
    log.critical(f'Error generating application {e.app_name} in environment {e.env_name}')
    exit(1)
  except InternalError:
    log.critical('Internal error')
    exit(1)
  except ConfigFileError:
    log.critical('Config file error')
    exit(1)
  except PathDoesNotExistError as e:
    log.critical(f'Path does not exist {e.path}')
    exit(1)
  except FileNotFoundError as e:
    log.critical(f'File or directory not found {e.filename}')
    exit(1)
  except Exception as e:
    raise e


def cli_entry_point() -> None:
  parser = argparse.ArgumentParser(prog='make-argocd-fly', description='Render ArgoCD Applications.')
  parser.add_argument('--root-dir', type=str, default=default.ROOT_DIR, help='Root directory (default: current directory)')
  parser.add_argument('--config-dir', type=str, default=default.CONFIG_DIR, help='Configuration files directory (default: config)')
  parser.add_argument('--source-dir', type=str, default=default.SOURCE_DIR, help='Source files directory (default: source)')
  parser.add_argument('--output-dir', type=str, default=default.OUTPUT_DIR, help='Output files directory (default: output)')
  parser.add_argument('--tmp-dir', type=str, default=default.TMP_DIR, help='Temporary files directory (default: .tmp)')
  parser.add_argument('--render-apps', type=str, default=None, help='Comma separate list of applications to render')
  parser.add_argument('--render-envs', type=str, default=None, help='Comma separate list of environments to render')
  parser.add_argument('--skip-generate', action='store_true', help='Skip resource generation')
  parser.add_argument('--preserve-tmp-dir', action='store_true', help='Preserve temporary directory')
  parser.add_argument('--remove-output-dir', action='store_true', help='Remove output directory')
  parser.add_argument('--print-vars', action='store_true', help='Print variables for each application (DEPRECATED)')
  parser.add_argument('--var-identifier', type=str, default=default.VAR_IDENTIFIER, help='Variable prefix in configuration files (default: $)')
  parser.add_argument('--skip-latest-version-check', action='store_true', help='Skip latest version check')
  parser.add_argument('--yaml-linter', action='store_true', help='Run yamllint against output directory (https://github.com/adrienverge/yamllint)')
  parser.add_argument('--kube-linter', action='store_true', help='Run kube-linter against output directory (https://github.com/stackrox/kube-linter)')
  parser.add_argument('--max-concurrent-apps', type=int, default=default.MAX_CONCURRENT_APPS,
                      help='Maximum number of applications to render concurrently (default: 8)')
  parser.add_argument('--max-subproc', type=int, default=default.MAX_SUBPROC,
                      help='Maximum number of subprocesses to run concurrently (default: number of CPU cores)')
  parser.add_argument('--dump-context', action='store_true', help='Dump per-stage context snapshots for debugging')
  parser.add_argument('--stats', action='store_true', help='Print execution time statistics per stage and per application')
  parser.add_argument('--max-io', type=int, default=default.MAX_IO, help='Maximum number of I/O operations to run concurrently (default: 32)')
  parser.add_argument('--loglevel', type=str, default=default.LOGLEVEL, help='DEBUG, INFO, WARNING, ERROR, CRITICAL')
  parser.add_argument('--version', action='version', version=f'{get_package_name()} {get_current_version()}', help='Show version')
  args = parser.parse_args()

  init_logging(args.loglevel)
  init_warnings()
  main(**vars(args))

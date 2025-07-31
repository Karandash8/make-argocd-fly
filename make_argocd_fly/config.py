import logging
import yaml
import glob
import os
from deprecated import deprecated

from make_argocd_fly import consts
from make_argocd_fly.cliparams import get_cli_params
from make_argocd_fly.params import Params
from make_argocd_fly.utils import build_path, merge_dicts_without_duplicates, merge_dicts_with_overrides, VarsResolver
from make_argocd_fly.exceptions import InternalError, ConfigFileError, MergeError


log = logging.getLogger(__name__)


class Config:
  def __init__(self) -> None:
    self.config = None
    self._source_dir = None
    self._output_dir = None
    self._tmp_dir = None

    self.cli_params = get_cli_params()

  def populate_config(self, **kwargs) -> None:
    self.__dict__.update(kwargs)

  @property
  def source_dir(self) -> str:
    if not self._source_dir:
      log.error('Config is not populated')
      raise InternalError

    return self._source_dir

  @property
  def output_dir(self) -> str:
    if not self._output_dir:
      log.error('Config is not populated')
      raise InternalError

    return self._output_dir

  @property
  def tmp_dir(self) -> str:
    if not self._tmp_dir:
      log.error('Config is not populated')
      raise InternalError

    return self._tmp_dir

  def list_envs(self) -> list[str]:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError

    if consts.KEYWORK_ENVS not in self.config:
      log.warning('Missing `envs` keyword in config')
      return []

    return list(self.config[consts.KEYWORK_ENVS].keys())

  def get_env(self, env_name: str) -> dict:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError

    if env_name not in self.list_envs():
      log.error(f'Environment {env_name} is not defined')
      raise ConfigFileError

    return self.config[consts.KEYWORK_ENVS][env_name]

  def list_apps(self, env_name: str) -> list[str]:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError

    env = self.get_env(env_name)
    if consts.KEYWORK_APPS not in env:
      log.warning(f'Missing `apps` keyword in environment {env_name}')
      return []

    return list(env[consts.KEYWORK_APPS].keys())

  def get_app(self, env_name: str, app_name: str) -> dict:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError

    env = self.get_env(env_name)
    if app_name not in self.list_apps(env_name):
      log.error(f'Application {app_name} is not defined in environment {env_name}')
      raise ConfigFileError

    return env[consts.KEYWORK_APPS][app_name]

  def _get_global_scope(self, keyword: str) -> dict:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError

    return self.config[keyword] if keyword in self.config else {}

  def _get_env_scope(self, keyword: str, env_name: str) -> dict:
    env = self.get_env(env_name)

    return env[keyword] if keyword in env else {}

  def _get_app_scope(self, keyword: str, env_name: str, app_name: str) -> dict:
    app = self.get_app(env_name, app_name)

    return app[keyword] if keyword in app else {}

  def get_vars(self, env_name: str | None = None, app_name: str | None = None, extra_vars: dict | None = None) -> dict:
    if extra_vars is None:
      extra_vars = {}

    global_vars = self._get_global_scope(consts.KEYWORK_VARS)
    env_vars = self._get_env_scope(consts.KEYWORK_VARS, env_name) if env_name else {}
    app_vars = self._get_app_scope(consts.KEYWORK_VARS, env_name, app_name) if env_name and app_name else {}

    resolved_vars = merge_dicts_with_overrides(
      extra_vars,
      VarsResolver.resolve_all(global_vars,
                               merge_dicts_with_overrides(extra_vars, global_vars),
                               var_identifier=self.cli_params.var_identifier,
                               allow_unresolved=True)
    )

    if env_name:
      resolved_vars = merge_dicts_with_overrides(
        resolved_vars,
        VarsResolver.resolve_all(env_vars,
                                 merge_dicts_with_overrides(resolved_vars, env_vars),
                                 var_identifier=self.cli_params.var_identifier,
                                 allow_unresolved=True)
      )

    if env_name and app_name:
      resolved_vars = merge_dicts_with_overrides(
        resolved_vars,
        VarsResolver.resolve_all(app_vars,
                                 merge_dicts_with_overrides(resolved_vars, app_vars),
                                 var_identifier=self.cli_params.var_identifier,
                                 allow_unresolved=True)
      )

    resolved_vars = VarsResolver.resolve_all(resolved_vars,
                                             resolved_vars,
                                             var_identifier=self.cli_params.var_identifier,
                                             allow_unresolved=False)

    return resolved_vars

  def get_params(self, env_name: str | None = None, app_name: str | None = None) -> Params:
    global_params = self._get_global_scope(consts.KEYWORK_PARAMS)
    env_params = self._get_env_scope(consts.KEYWORK_PARAMS, env_name) if env_name else {}
    app_params = self._get_app_scope(consts.KEYWORK_PARAMS, env_name, app_name) if env_name and app_name else {}

    params = Params()
    params.populate_params(**merge_dicts_with_overrides(global_params, env_params, app_params))

    return params

  def get_app_params_deprecated(self, env_name: str, app_name: str) -> dict:
    app = self.get_app(env_name, app_name)
    app_params = {key: value for key, value in app.items() if
                  (key != consts.KEYWORK_VARS) and (key != consts.KEYWORK_PARAMS)}

    return self.return_app_params_deprecated(app_params) if app_params else {}

  @deprecated(version='v0.2.15', reason='Application parameters under application definition are deprecated, use scoped `params` keyword instead')
  def return_app_params_deprecated(self, params: dict) -> dict:
    return params


config = Config()


def _list_config_files(config_dir: str) -> list[str]:
  config_files = glob.glob('*.yml', root_dir=config_dir)

  if not config_files:
    log.error(f'No config files found in {config_dir}')
    raise InternalError

  return config_files


def _read_config_file(config_file: str) -> dict:
  config_content = {}

  try:
    with open(config_file) as f:
      config_content = yaml.safe_load(f.read())
  except FileNotFoundError:
    log.error(f'Config file {config_file} not found')
    raise InternalError
  except yaml.YAMLError:
    log.error(f'Invalid YAML config file {config_file}')
    raise ConfigFileError

  return config_content


@deprecated(version='v0.2.14', reason='`--config-file` is deprecated, use `--config-dir` instead')
def read_config_file():
  pass


def populate_config(root_dir: str = consts.DEFAULT_ROOT_DIR,
                    config_file: str = consts.DEFAULT_CONFIG_FILE,  # DEPRECATED
                    config_dir: str = consts.DEFAULT_CONFIG_DIR,
                    source_dir: str = consts.DEFAULT_SOURCE_DIR,
                    output_dir: str = consts.DEFAULT_OUTPUT_DIR,
                    tmp_dir: str = consts.DEFAULT_TMP_DIR) -> Config:
  try:
    config_files = _list_config_files(build_path(root_dir, config_dir))
    merged_config = merge_dicts_without_duplicates(*[_read_config_file(os.path.join(build_path(root_dir, config_dir),
                                                                                    config_file)) for config_file in config_files])
  except InternalError:
    read_config_file()
    merged_config = _read_config_file(build_path(root_dir, config_file))
  except MergeError:
    log.error('Error merging config files')
    raise ConfigFileError

  config.populate_config(config=merged_config,
                         _source_dir=build_path(root_dir, source_dir),
                         _output_dir=build_path(root_dir, output_dir, allow_missing=True),
                         _tmp_dir=build_path(root_dir, tmp_dir, allow_missing=True))

  log.debug(f'Source directory: {config.source_dir}')
  log.debug(f'Output directory: {config.output_dir}')
  log.debug(f'Temporary directory: {config.tmp_dir}')

  return config


def get_config() -> Config:
  return config

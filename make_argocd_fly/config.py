import logging
import yaml
import glob
import os
from deprecated import deprecated

from make_argocd_fly import consts
from make_argocd_fly.utils import build_path, merge_dicts_without_duplicates
from make_argocd_fly.exceptions import InternalError, ConfigFileError, MergeError


log = logging.getLogger(__name__)


class Config:
  def __init__(self) -> None:
    self.config = None
    self._source_dir = None
    self._output_dir = None
    self._tmp_dir = None

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

  def get_envs(self) -> dict:
    return self.config[consts.KEYWORK_ENVS] if consts.KEYWORK_ENVS in self.config else {}

  def get_global_vars(self) -> dict:
    return self.config[consts.KEYWORK_VARS] if consts.KEYWORK_VARS in self.config else {}

  def get_env_vars(self, env_name: str) -> dict:
    envs = self.get_envs()
    if env_name not in envs:
      log.error('Environment {} is not defined'.format(env_name))
      raise ConfigFileError

    return envs[env_name][consts.KEYWORK_VARS] if consts.KEYWORK_VARS in envs[env_name] else {}

  def get_app_vars(self, env_name: str, app_name: str) -> dict:
    envs = self.get_envs()
    if env_name not in envs:
      log.error('Environment {} is not defined'.format(env_name))
      raise ConfigFileError

    if consts.KEYWORK_APPS not in envs[env_name] or app_name not in envs[env_name][consts.KEYWORK_APPS]:
      log.error('Application {} is not defined in environment {}'.format(app_name, env_name))
      raise ConfigFileError

    if consts.KEYWORK_VARS in envs[env_name][consts.KEYWORK_APPS][app_name]:
      return envs[env_name][consts.KEYWORK_APPS][app_name][consts.KEYWORK_VARS]
    else:
      return {}

  def get_app_params(self, env_name: str, app_name: str) -> dict:
    envs = self.get_envs()
    if env_name not in envs:
      log.error('Environment {} is not defined'.format(env_name))
      raise ConfigFileError

    if consts.KEYWORK_APPS not in envs[env_name] or app_name not in envs[env_name][consts.KEYWORK_APPS]:
      log.error('Application {} is not defined in environment {}'.format(app_name, env_name))
      raise ConfigFileError

    return {key: value for key, value in envs[env_name][consts.KEYWORK_APPS][app_name].items() if key != consts.KEYWORK_VARS}


config = Config()


def _list_config_files(config_dir: str) -> list[str]:
  config_files = glob.glob('*.yml', root_dir=config_dir)

  if not config_files:
    log.error('No config files found in {}'.format(config_dir))
    raise InternalError

  return config_files


def _read_config_file(config_file: str) -> dict:
  config_content = {}

  try:
    with open(config_file) as f:
      config_content = yaml.safe_load(f.read())
  except FileNotFoundError:
    log.error('Config file {} not found'.format(config_file))
    raise InternalError
  except yaml.YAMLError:
    log.error('Invalid YAML config file {}'.format(config_file))
    raise ConfigFileError

  return config_content


@deprecated(version='v0.2.14', reason="--config-file is deprecated, use --config-dir instead")
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

  log.debug('Source directory: {}'.format(config.source_dir))
  log.debug('Output directory: {}'.format(config.output_dir))
  log.debug('Temporary directory: {}'.format(config.tmp_dir))

  return config


def get_config() -> Config:
  return config

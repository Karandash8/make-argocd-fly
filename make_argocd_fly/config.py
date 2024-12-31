import logging
import os
import yaml

from make_argocd_fly import consts


log = logging.getLogger(__name__)


# TODO: use getter decorators
class Config:
  def __init__(self) -> None:
    self.source_dir = consts.DEFAULT_SOURCE_DIR
    self.output_dir = consts.DEFAULT_OUTPUT_DIR
    self.tmp_dir = consts.DEFAULT_TMP_DIR
    self.envs = consts.DEFAULT_ENVS
    self.global_vars = consts.DEFAULT_GLOBAL_VARS

  def init_config(self, root_dir: str, config: dict, source_dir: str, output_dir: str, tmp_dir: str) -> None:
    self.root_dir = root_dir
    self.source_dir = source_dir
    self.output_dir = output_dir
    self.tmp_dir = tmp_dir
    self.envs = config['envs'] if 'envs' in config else consts.DEFAULT_ENVS
    self.global_vars = config['vars'] if 'vars' in config else consts.DEFAULT_GLOBAL_VARS

  def get_source_dir(self) -> str:
    return get_abs_path(self.root_dir, self.source_dir)

  def get_output_dir(self) -> str:
    return get_abs_path(self.root_dir, self.output_dir, allow_missing=True)

  def get_tmp_dir(self) -> str:
    return get_abs_path(self.root_dir, self.tmp_dir, allow_missing=True)

  def get_envs(self) -> dict:
    if not isinstance(self.envs, dict):
      log.error('Config was not initialized.')
      raise Exception
    return self.envs

  def get_global_vars(self) -> dict:
    if not isinstance(self.global_vars, dict):
      log.error('Config was not initialized.')
      raise Exception
    return self.global_vars

  def get_env_vars(self, env_name: str) -> dict:
    envs = self.get_envs()
    if env_name not in envs:
      log.error('Environment {} is not defined'.format(env_name))
      raise Exception
    return envs[env_name]['vars'] if 'vars' in envs[env_name] else {}

  def get_app_vars(self, env_name: str, app_name: str) -> dict:
    envs = self.get_envs()
    if env_name not in envs:
      log.error('Environment {} is not defined'.format(env_name))
      raise Exception

    if app_name not in envs[env_name]['apps']:
      log.error('Application {} is not defined in environment {}'.format(app_name, env_name))
      raise Exception

    return envs[env_name]['apps'][app_name]['vars'] if 'vars' in envs[env_name]['apps'][app_name] else {}

  def get_app_params(self, env_name: str, app_name: str) -> dict:
    envs = self.get_envs()
    if env_name not in envs:
      log.error('Environment {} is not defined'.format(env_name))
      raise Exception

    if app_name not in envs[env_name]['apps']:
      log.error('Application {} is not defined in environment {}'.format(app_name, env_name))
      raise Exception

    params = {}
    for key, value in envs[env_name]['apps'][app_name].items():
      if key != 'vars':
        params[key] = value

    return params


config = Config()


def get_abs_path(root_dir: str, path: str, allow_missing: bool = False) -> str:
  if not path:
    log.error('Path is empty.')
    raise Exception

  if os.path.isabs(path):
    abs_path = path
  else:
    abs_path = os.path.join(root_dir, path)

  if (not allow_missing) and (not os.path.exists(abs_path)):
    log.error('Path does not exist: {}'.format(abs_path))
    raise Exception

  return abs_path


def read_config(root_dir: str = consts.DEFAULT_ROOT_DIR,
                config_file: str = consts.DEFAULT_CONFIG_FILE,
                source_dir: str = consts.DEFAULT_SOURCE_DIR,
                output_dir: str = consts.DEFAULT_OUTPUT_DIR,
                tmp_dir: str = consts.DEFAULT_TMP_DIR) -> Config:
  root_dir = os.path.abspath(root_dir)
  config_content = {}

  with open(get_abs_path(root_dir, config_file)) as f:
    config_content = yaml.safe_load(f.read())

  config.init_config(root_dir, config_content, source_dir, output_dir, tmp_dir)

  log.debug('Root directory: {}'.format(root_dir))
  log.debug('Config file: {}'.format(get_abs_path(root_dir, config_file)))
  log.debug('Source directory: {}'.format(config.get_source_dir()))
  log.debug('Output directory: {}'.format(config.get_output_dir()))
  log.debug('Temporary directory: {}'.format(config.get_tmp_dir()))

  return config


def get_config() -> Config:
  return config

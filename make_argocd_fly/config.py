import logging
import os
import yaml

SOURCE_DIR = 'source'
OUTPUT_DIR = 'output'
TMP_DIR = '.tmp'
ENVS = {}
VARS = {}

log = logging.getLogger(__name__)


class Config:
  def __init__(self) -> None:
    self.source_dir = None
    self.output_dir = None
    self.tmp_dir = None
    self.envs = None
    self.vars = None

  def init_config(self, root_dir: str, config: dict) -> None:
    self.root_dir = root_dir

    self.source_dir = config['source_dir'] if 'source_dir' in config else SOURCE_DIR
    self.output_dir = config['output_dir'] if 'output_dir' in config else OUTPUT_DIR
    self.tmp_dir = config['tmp_dir'] if 'tmp_dir' in config else TMP_DIR
    self.envs = config['envs'] if 'envs' in config else ENVS
    self.vars = config['vars'] if 'vars' in config else VARS

  def get_source_dir(self) -> str:
    if not self.source_dir:
      log.error('Config was not initialized.')
      raise Exception

    return os.path.join(self.root_dir, self.source_dir)

  def get_output_dir(self) -> str:
    if not self.output_dir:
      log.error('Config was not initialized.')
      raise Exception

    return os.path.join(self.root_dir, self.output_dir)

  def get_tmp_dir(self) -> str:
    if not self.tmp_dir:
      log.error('Config was not initialized.')
      raise Exception

    return os.path.join(self.root_dir, self.tmp_dir)

  def get_envs(self) -> dict:
    if not self.envs:
      log.error('Config was not initialized.')
      raise Exception

    return self.envs

  def get_vars(self) -> str:
    if not self.envs:
      log.error('Config was not initialized.')
      raise Exception

    return self.vars


config = Config()


def read_config(root_dir: str, config_file: str) -> Config:
  config_content = {}
  try:
    with open(os.path.join(root_dir, config_file)) as f:
      config_content = yaml.safe_load(f.read())
  except FileNotFoundError as error:
    log.error('Config file is missing')
    log.fatal(error)
    raise

  config.init_config(root_dir, config_content)

  return config

def get_config() -> Config:
  return config

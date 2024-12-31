import os

DEFAULT_ROOT_DIR = os.getcwd()
DEFAULT_CONFIG_FILE = 'config.yml'
DEFAULT_SOURCE_DIR = 'source'
DEFAULT_OUTPUT_DIR = 'output'
DEFAULT_TMP_DIR = '.tmp'
DEFAULT_LOG_CONFIG_FILE = 'log_config.yml'
DEFAULT_ENVS = {}
DEFAULT_GLOBAL_VARS = {}
DEFAULT_VAR_IDENTIFIER = '$'
DEFAULT_LOGLEVEL = 'INFO'


class AppParamsNames:
  APP_DEPLOYER = 'app_deployer'
  APP_DEPLOYER_ENV = 'app_deployer_env'
  NON_K8S_FILES_TO_RENDER = 'non_k8s_files_to_render'
  EXCLUDE_RENDERING = 'exclude_rendering'

  @classmethod
  def get_names(cls) -> list[str]:
    return [getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))]

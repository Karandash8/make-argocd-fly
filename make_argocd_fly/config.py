import logging
import yaml
from enum import StrEnum, auto

from make_argocd_fly import default
from make_argocd_fly.cliparam import get_cli_params
from make_argocd_fly.param import Params
from make_argocd_fly.util import build_path, merge_dicts_without_duplicates, merge_dicts_with_overrides, VarsResolver
from make_argocd_fly.exception import InternalError, ConfigFileError, MergeError
from make_argocd_fly.resource.viewer import build_scoped_viewer, ResourceType


log = logging.getLogger(__name__)


class ConfigKeywords(StrEnum):
  ENVS = auto()
  APPS = auto()
  VARS = auto()
  PARAMS = auto()


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
      raise InternalError()

    return self._source_dir

  @property
  def output_dir(self) -> str:
    if not self._output_dir:
      log.error('Config is not populated')
      raise InternalError()

    return self._output_dir

  @property
  def tmp_dir(self) -> str:
    if not self._tmp_dir:
      log.error('Config is not populated')
      raise InternalError()

    return self._tmp_dir

  def list_envs(self) -> list[str]:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError()

    if ConfigKeywords.ENVS not in self.config:
      log.warning('Missing `envs` keyword in config')
      return []

    return list(self.config[ConfigKeywords.ENVS].keys())

  def get_env(self, env_name: str) -> dict:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError()

    if env_name not in self.list_envs():
      log.error(f'Environment {env_name} is not defined')
      raise ConfigFileError

    return self.config[ConfigKeywords.ENVS][env_name]

  def list_filtered_envs(self) -> list[str]:
    """Return envs filtered according to --render-envs, if provided."""
    envs = self.list_envs()
    render_envs = self.cli_params.render_envs

    if not render_envs:
      return envs

    selected = set(render_envs.split(','))
    return [env for env in envs if env in selected]

  def list_apps(self, env_name: str) -> list[str]:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError()

    env = self.get_env(env_name)
    if ConfigKeywords.APPS not in env:
      log.warning(f'Missing `apps` keyword in environment {env_name}')
      return []

    return list(env[ConfigKeywords.APPS].keys())

  def list_filtered_apps(self, env_name: str) -> list[str]:
    """Return apps in env filtered according to --render-apps, if provided."""
    apps = self.list_apps(env_name)
    render_apps = self.cli_params.render_apps
    if not render_apps:
      return apps

    selected = set(render_apps.split(','))
    return [app for app in apps if app in selected]

  def get_app(self, env_name: str, app_name: str) -> dict:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError()

    env = self.get_env(env_name)
    if app_name not in self.list_apps(env_name):
      log.error(f'Application {app_name} is not defined in environment {env_name}')
      raise ConfigFileError

    return env[ConfigKeywords.APPS][app_name]

  def _get_global_scope(self, keyword: ConfigKeywords) -> dict:
    if self.config is None:
      log.error('Config is not populated')
      raise InternalError()

    return self.config[keyword] if keyword in self.config else {}

  def _get_env_scope(self, keyword: ConfigKeywords, env_name: str) -> dict:
    env = self.get_env(env_name)

    return env[keyword] if keyword in env else {}

  def _get_app_scope(self, keyword: ConfigKeywords, env_name: str, app_name: str) -> dict:
    app = self.get_app(env_name, app_name)

    return app[keyword] if keyword in app else {}

  def get_vars(self, env_name: str | None = None, app_name: str | None = None, extra_vars: dict | None = None) -> dict:
    if extra_vars is None:
      extra_vars = {}

    global_vars = self._get_global_scope(ConfigKeywords.VARS)
    env_vars = self._get_env_scope(ConfigKeywords.VARS, env_name) if env_name else {}
    app_vars = self._get_app_scope(ConfigKeywords.VARS, env_name, app_name) if env_name and app_name else {}

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
                                             allow_unresolved=True)

    return resolved_vars

  def get_params(self, env_name: str | None = None, app_name: str | None = None) -> Params:
    global_params = self._get_global_scope(ConfigKeywords.PARAMS)
    env_params = self._get_env_scope(ConfigKeywords.PARAMS, env_name) if env_name else {}
    app_params = self._get_app_scope(ConfigKeywords.PARAMS, env_name, app_name) if env_name and app_name else {}

    params = Params()
    try:
      params.populate_params(**merge_dicts_with_overrides(global_params, env_params, app_params))
    except ConfigFileError as e:
      log.error(f'Error populating params for application {app_name} in environment {env_name}')
      raise e

    return params


config = Config()


def populate_config(root_dir: str = default.ROOT_DIR,
                    config_dir: str = default.CONFIG_DIR,
                    source_dir: str = default.SOURCE_DIR,
                    output_dir: str = default.OUTPUT_DIR,
                    tmp_dir: str = default.TMP_DIR) -> Config:
  try:
    viewer = build_scoped_viewer(build_path(root_dir, config_dir))
    yml_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML], template=False))

    config_files_content = []
    for child in yml_children:
      log.debug(f'Found config file: {child.rel_path}')
      try:
        config_files_content.append(yaml.safe_load(child.content))
      except yaml.YAMLError:
        log.error(f'Invalid YAML in config file {child.rel_path}')
        raise ConfigFileError

    merged_config = merge_dicts_without_duplicates(*config_files_content)
  except MergeError:
    log.error('Error merging config files')
    raise ConfigFileError

  config.populate_config(config=merged_config,
                         _source_dir=build_path(root_dir, source_dir),
                         _output_dir=build_path(root_dir, output_dir, allow_missing=True),
                         _tmp_dir=build_path(root_dir, tmp_dir, allow_missing=True))

  log.debug(f'Config directory: {build_path(root_dir, config_dir)}')
  log.debug(f'Source directory: {config.source_dir}')
  log.debug(f'Output directory: {config.output_dir}')
  log.debug(f'Temporary directory: {config.tmp_dir}')

  return config


def get_config() -> Config:
  return config

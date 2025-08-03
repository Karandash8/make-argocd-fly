import logging

from make_argocd_fly import const


log = logging.getLogger(__name__)


class CLIParams:
  def __init__(self) -> None:
    self.root_dir = const.DEFAULT_ROOT_DIR
    self.config_dir = const.DEFAULT_CONFIG_DIR
    self.source_dir = const.DEFAULT_SOURCE_DIR
    self.output_dir = const.DEFAULT_OUTPUT_DIR
    self.tmp_dir = const.DEFAULT_TMP_DIR
    self.render_apps = None
    self.render_envs = None
    self.skip_generate = False
    self.preserve_tmp_dir = False
    self.remove_output_dir = False
    self.print_vars = False
    self.var_identifier = const.DEFAULT_VAR_IDENTIFIER
    self.skip_latest_version_check = False
    self.yaml_linter = False
    self.kube_linter = False
    self.loglevel = const.DEFAULT_LOGLEVEL

  def populate_cli_params(self, **kwargs) -> None:
    self.__dict__.update(kwargs)


cli_params = CLIParams()


def populate_cli_params(**kwargs) -> CLIParams:
  cli_params.populate_cli_params(**kwargs)

  return cli_params


def get_cli_params() -> CLIParams:
  return cli_params

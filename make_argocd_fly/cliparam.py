import logging

from make_argocd_fly import default


log = logging.getLogger(__name__)


class CLIParams:
  def __init__(self) -> None:
    self.root_dir = default.ROOT_DIR
    self.config_dir = default.CONFIG_DIR
    self.source_dir = default.SOURCE_DIR
    self.output_dir = default.OUTPUT_DIR
    self.tmp_dir = default.TMP_DIR
    self.render_apps = None
    self.render_envs = None
    self.skip_generate = False
    self.preserve_tmp_dir = False
    self.remove_output_dir = False
    self.print_vars = False
    self.var_identifier = default.VAR_IDENTIFIER
    self.skip_latest_version_check = False
    self.yaml_linter = False
    self.kube_linter = False
    self.loglevel = default.LOGLEVEL
    self.max_concurrent_apps = default.MAX_CONCURRENT_APPS
    self.max_subproc = default.MAX_SUBPROC
    self.max_io = default.MAX_IO
    self.dump_context = False
    self.stats = False

  def populate_cli_params(self, **kwargs) -> None:
    self.__dict__.update(kwargs)


cli_params = CLIParams()


def populate_cli_params(**kwargs) -> CLIParams:
  cli_params.populate_cli_params(**kwargs)

  return cli_params


def get_cli_params() -> CLIParams:
  return cli_params

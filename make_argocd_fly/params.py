import logging

from make_argocd_fly import consts


log = logging.getLogger(__name__)


class Params:
  def __init__(self) -> None:
    self.root_dir = consts.DEFAULT_ROOT_DIR
    self.config_file = consts.DEFAULT_CONFIG_FILE
    self.source_dir = consts.DEFAULT_SOURCE_DIR
    self.output_dir = consts.DEFAULT_OUTPUT_DIR
    self.tmp_dir = consts.DEFAULT_TMP_DIR
    self.render_apps = None
    self.render_envs = None
    self.skip_generate = False
    self.preserve_tmp_dir = False
    self.remove_output_dir = False
    self.print_vars = False
    self.var_identifier = consts.DEFAULT_VAR_IDENTIFIER
    self.skip_latest_version_check = False
    self.yaml_linter = False
    self.kube_linter = False
    self.loglevel = consts.DEFAULT_LOGLEVEL

  def populate_params(self, **kwargs) -> None:
    self.__dict__.update(kwargs)


params = Params()


def populate_params(**kwargs) -> Params:
  params.populate_params(**kwargs)

  return params


def get_params() -> Params:
  return params

import logging

from make_argocd_fly import defaults


log = logging.getLogger(__name__)


class Params:
  def __init__(self) -> None:
    self.root_dir = defaults.ROOT_DIR
    self.config_file = defaults.CONFIG_FILE
    self.source_dir = defaults.SOURCE_DIR
    self.output_dir = defaults.OUTPUT_DIR
    self.tmp_dir = defaults.TMP_DIR
    self.render_apps = None
    self.render_envs = None
    self.skip_generate = False
    self.preserve_tmp_dir = False
    self.remove_output_dir = False
    self.print_vars = False
    self.var_identifier = defaults.VAR_IDENTIFIER
    self.skip_latest_version_check = False
    self.yaml_linter = False
    self.kube_linter = False
    self.loglevel = defaults.LOGLEVEL

  def populate_params(self, **kwargs) -> None:
    self.__dict__.update(kwargs)

  def get_root_dir(self):
    return self.root_dir

  def get_config_file(self):
    return self.config_file

  def get_source_dir(self):
    return self.source_dir

  def get_output_dir(self):
    return self.output_dir

  def get_tmp_dir(self):
    return self.tmp_dir

  def get_render_apps(self):
    return self.render_apps

  def get_render_envs(self):
    return self.render_envs

  def get_skip_generate(self):
    return self.skip_generate

  def get_preserve_tmp_dir(self):
    return self.preserve_tmp_dir

  def get_remove_output_dir(self):
    return self.remove_output_dir

  def get_print_vars(self):
    return self.print_vars

  def get_var_identifier(self):
    return self.var_identifier

  def get_skip_latest_version_check(self):
    return self.skip_latest_version_check

  def get_yaml_linter(self):
    return self.yaml_linter

  def get_kube_linter(self):
    return self.kube_linter

  def get_loglevel(self):
    return self.loglevel


params = Params()


def populate_params(**kwargs) -> Params:
  params.populate_params(**kwargs)


def get_params() -> Params:
  return params

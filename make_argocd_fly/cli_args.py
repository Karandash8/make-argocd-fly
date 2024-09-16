import logging


log = logging.getLogger(__name__)


class CLIArgs:
  def __init__(self) -> None:
    self.root_dir = None
    self.config_file = None
    self.source_dir = None
    self.output_dir = None
    self.tmp_dir = None
    self.render_apps = None
    self.render_envs = None
    self.skip_generate = None
    self.preserve_tmp_dir = None
    self.remove_output_dir = None
    self.print_vars = None
    self.var_identifier = None
    self.skip_latest_version_check = None
    self.yaml_linter = None
    self.kube_linter = None
    self.loglevel = None

  def init_config(self, **kwargs) -> None:
    self.__dict__.update(kwargs)

  def get_root_dir(self):
    if self.root_dir is None:
      raise Exception("root_dir is not set")
    return self.root_dir

  def get_config_file(self):
    if self.config_file is None:
      raise Exception("config_file is not set")
    return self.config_file

  def get_source_dir(self):
    if self.source_dir is None:
      raise Exception("source_dir is not set")
    return self.source_dir

  def get_output_dir(self):
    if self.output_dir is None:
      raise Exception("output_dir is not set")
    return self.output_dir

  def get_tmp_dir(self):
    if self.tmp_dir is None:
      raise Exception("tmp_dir is not set")
    return self.tmp_dir

  def get_render_apps(self):
    return self.render_apps

  def get_render_envs(self):
    return self.render_envs

  def get_skip_generate(self):
    if self.skip_generate is None:
      raise Exception("skip_generate is not set")
    return self.skip_generate

  def get_preserve_tmp_dir(self):
    if self.preserve_tmp_dir is None:
      raise Exception("preserve_tmp_dir is not set")
    return self.preserve_tmp_dir

  def get_remove_output_dir(self):
    if self.remove_output_dir is None:
      raise Exception("remove_output_dir is not set")
    return self.remove_output_dir

  def get_print_vars(self):
    if self.print_vars is None:
      raise Exception("print_vars is not set")
    return self.print_vars

  def get_var_identifier(self):
    if self.var_identifier is None:
      raise Exception("var_identifier is not set")
    return self.var_identifier

  def get_skip_latest_version_check(self):
    if self.skip_latest_version_check is None:
      raise Exception("skip_latest_version_check is not set")
    return self.skip_latest_version_check

  def get_yaml_linter(self):
    if self.yaml_linter is None:
      raise Exception("yaml_linter is not set")
    return self.yaml_linter

  def get_kube_linter(self):
    if self.kube_linter is None:
      raise Exception("kube_linter is not set")
    return self.kube_linter

  def get_loglevel(self):
    if self.loglevel is None:
      raise Exception("loglevel is not set")
    return self.loglevel


cli_args = CLIArgs()


def populate_cli_args(**kwargs) -> CLIArgs:
  cli_args.init_config(**kwargs)

  return cli_args


def get_cli_args() -> CLIArgs:
  return cli_args

class BaseError(Exception):
  pass


class MissingDirectoryError(BaseError):
  def __init__(self, directory: str) -> None:
    self.directory = directory
    super().__init__('Missing directory {}'.format(directory))


class MissingApplicationDirectoryError(BaseError):
  def __init__(self, directory: str) -> None:
    self.directory = directory
    super().__init__('Missing application directory {}'.format(directory))


class UnpopulatedConfigError(BaseError):
  def __init__(self) -> None:
    super().__init__('Config is not populated')


class MissingConfigFileError(BaseError):
  def __init__(self, config_file: str) -> None:
    self.directory = config_file
    super().__init__('Missing config file {}'.format(config_file))


class InvalidConfigFileError(BaseError):
  def __init__(self, config_file: str) -> None:
    self.directory = config_file
    super().__init__('Invalid YAML config file {}'.format(config_file))


class UnknownEnvirontmentError(BaseError):
  def __init__(self, env_name: str) -> None:
    self.env_name = env_name
    super().__init__('Unknown environment {}'.format(env_name))


class UnknownApplicationError(BaseError):
  def __init__(self, app_name: str, env_name: str) -> None:
    self.app_name = app_name
    self.env_name = env_name
    super().__init__('Unknown application {} in environment {}'.format(app_name, env_name))

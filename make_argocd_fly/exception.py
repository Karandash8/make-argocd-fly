class BaseError(Exception):
  pass


class InternalError(BaseError):
  def __init__(self) -> None:
    super().__init__('Internal error')


class ConfigFileError(BaseError):
  def __init__(self) -> None:
    super().__init__('Config file error')


class MergeError(BaseError):
  def __init__(self) -> None:
    super().__init__('Error merging dictionaries')


class UndefinedTemplateVariableError(BaseError):
  def __init__(self, variable_name: str) -> None:
    super().__init__(f'Variable {variable_name} is undefined')


class TemplateRenderingError(BaseError):
  def __init__(self, template_filename: str, app_name: str, env_name: str) -> None:
    self.template_filename = template_filename
    self.app_name = app_name
    self.env_name = env_name
    super().__init__(f'Error rendering template {template_filename}')


class YamlError(BaseError):
  def __init__(self, app_name: str, env_name: str) -> None:
    self.app_name = app_name
    self.env_name = env_name
    super().__init__(f'YAML error in application {app_name} in environment {env_name}')


class PathDoesNotExistError(BaseError):
  def __init__(self, path: str) -> None:
    self.path = path
    super().__init__(f'Path does not exist {path}')


class KustomizeError(BaseError):
  def __init__(self, app_name: str, env_name: str) -> None:
    self.app_name = app_name
    self.env_name = env_name
    super().__init__(f'Error running kustomize for application {app_name} in environment {env_name}')


class HelmfileError(BaseError):
  def __init__(self, app_name: str, env_name: str) -> None:
    self.app_name = app_name
    self.env_name = env_name
    super().__init__(f'Error running helmfile for application {app_name} in environment {env_name}')


class UnknownJinja2Error(BaseError):
  def __init__(self) -> None:
    super().__init__('Unknown error in jinja2 template')


class OutputFilenameConstructionError(BaseError):
  def __init__(self, key: str | None = None) -> None:
    _msg = f'(hint: missing key \'{key}\')' if key else '(required fields missing)'

    super().__init__(_msg)


class YamlObjectRequiredError(BaseError):
  def __init__(self) -> None:
    super().__init__('YamlWriter requires a mapping (dict) yaml_obj payload')

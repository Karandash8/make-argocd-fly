class MakeArgoCDFlyError(Exception):
  '''Base class for all project-specific exceptions.'''


class UserError(MakeArgoCDFlyError):
  '''Invalid user input, config, templates, paths, or application content.'''


class InternalError(MakeArgoCDFlyError):
  '''Programming error or unexpected internal state.'''

  def __init__(self, message: str = 'Internal error') -> None:
    super().__init__(message)


class AppError(UserError):
  def __init__(self, message: str, app_name: str, env_name: str) -> None:
    self.app_name = app_name
    self.env_name = env_name
    super().__init__(message)


class ExternalToolError(AppError):
  '''Failure of an external tool such as kustomize or helmfile.'''

  def __init__(self, tool: str, app_name: str, env_name: str, message: str | None = None) -> None:
    self.tool = tool
    super().__init__(message or f'Error running {tool} for application {app_name} in environment {env_name}',
                     app_name,
                     env_name)


class PathDoesNotExistError(UserError):
  def __init__(self, path: str) -> None:
    self.path = path
    super().__init__(f'Path does not exist {path}')


class ConfigFileError(UserError):
  def __init__(self, message: str = 'Config file error') -> None:
    super().__init__(message)


class MergeError(InternalError):
  def __init__(self, message: str = 'Error merging dictionaries') -> None:
    super().__init__(message)


class UndefinedTemplateVariableError(UserError):
  def __init__(self, variable_name: str) -> None:
    self.variable_name = variable_name
    super().__init__(f'Variable {variable_name} is undefined')


class TemplateRenderingError(AppError):
  def __init__(self, template_filename: str, app_name: str, env_name: str) -> None:
    self.template_filename = template_filename
    super().__init__(f'Error rendering template {template_filename}',
                     app_name,
                     env_name)


class YamlError(AppError):
  def __init__(self, app_name: str, env_name: str, message: str | None = None) -> None:
    super().__init__(message or f'YAML error in application {app_name} in environment {env_name}',
                     app_name,
                     env_name)


class KustomizeError(ExternalToolError):
  def __init__(self, app_name: str, env_name: str) -> None:
    super().__init__('kustomize', app_name, env_name)


class HelmfileError(ExternalToolError):
  def __init__(self, app_name: str, env_name: str) -> None:
    super().__init__('helmfile', app_name, env_name)


class UnknownJinja2Error(InternalError):
  def __init__(self, message: str = 'Unknown error in jinja2 template') -> None:
    super().__init__(message)


class OutputFilenameConstructionError(UserError):
  def __init__(self, key: str | None = None) -> None:
    self.key = key
    if key is None:
      super().__init__('Required fields are missing for output filename construction')
    else:
      super().__init__(f'Missing key \'{key}\' for output filename construction')


class YamlObjectRequiredError(InternalError):
  def __init__(self) -> None:
    super().__init__('YamlWriter requires a mapping (dict) yaml_obj payload')

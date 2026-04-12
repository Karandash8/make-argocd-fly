class MakeArgoCDFlyError(Exception):
  '''Base class for all project-specific exceptions.'''


class UserError(MakeArgoCDFlyError):
  '''Invalid user input, config, templates, paths, or application content.'''


class InternalError(MakeArgoCDFlyError):
  '''Programming error or unexpected internal state.'''


class AppError(UserError):
  def __init__(self, app_name: str, env_name: str, message: str) -> None:
    self.app_name = app_name
    self.env_name = env_name
    super().__init__(message)


class PathDoesNotExistError(UserError):
  def __init__(self, path: str, message: str | None = None) -> None:
    self.path = path
    super().__init__(message or f'Path does not exist `{path}`')


class ConfigFileError(UserError):
  def __init__(self, message: str | None = None) -> None:
    super().__init__(message or 'Config file error')


class UndefinedTemplateVariableError(UserError):
  def __init__(self, variable_name: str, message: str | None = None) -> None:
    self.variable_name = variable_name
    super().__init__(message or f'Variable {variable_name} is undefined')


class OutputFilenameConstructionError(UserError):
  def __init__(self, key: str | None = None, message: str | None = None) -> None:
    self.key = key
    default = f"Missing key '{key}' for output filename construction" if key else \
              'Required fields are missing for output filename construction'
    super().__init__(message or default)


class MergeError(UserError):
  def __init__(self, message: str | None = None) -> None:
    super().__init__(message or 'Error merging dictionaries')


class TemplateRenderingError(AppError):
  def __init__(self, template_filename: str, app_name: str, env_name: str, message: str | None = None) -> None:
    self.template_filename = template_filename
    super().__init__(app_name, env_name, message or f'Error rendering template {template_filename}')


class ExternalToolError(AppError):
  '''Failure of an external tool such as kustomize or helmfile.'''

  def __init__(self, tool: str, app_name: str, env_name: str, message: str | None = None) -> None:
    self.tool = tool
    super().__init__(app_name, env_name, message or f'Error during execution of `{tool}` binary')


class KustomizeError(ExternalToolError):
  def __init__(self, app_name: str, env_name: str, message: str | None = None) -> None:
    super().__init__('kustomize', app_name, env_name, message)


class HelmfileError(ExternalToolError):
  def __init__(self, app_name: str, env_name: str, message: str | None = None) -> None:
    super().__init__('helmfile', app_name, env_name, message)

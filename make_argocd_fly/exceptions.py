class BaseError(Exception):
  pass


class MissingApplicationDirectoryError(BaseError):
  def __init__(self, directory: str) -> None:
    self.directory = directory
    super().__init__('Missing application directory {}'.format(directory))


class InternalError(BaseError):
  def __init__(self) -> None:
    super().__init__('Internal error')


class ConfigFileError(BaseError):
  def __init__(self) -> None:
    super().__init__('Config file error')


class UndefinedTemplateVariableError(BaseError):
  def __init__(self, variable_name: str) -> None:
    super().__init__('Variable {} is undefined'.format(variable_name))


class TemplateRenderingError(BaseError):
  def __init__(self, template_filename: str, app_name: str, env_name: str) -> None:
    self.template_filename = template_filename
    self.app_name = app_name
    self.env_name = env_name
    super().__init__('Error rendering template {}'.format(template_filename))


class UnknownJinja2Error(BaseError):
  def __init__(self) -> None:
    super().__init__('Unknown error in jinja2 template')

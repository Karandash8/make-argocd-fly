import logging
from enum import StrEnum, auto

from make_argocd_fly.exception import ConfigFileError

log = logging.getLogger(__name__)


class ApplicationNameFormat(StrEnum):
  SHORT = auto()
  FULL = auto()


class ApplicationTypes(StrEnum):
  K8S = auto()
  GENERIC = auto()


class ParamNames(StrEnum):
  APP_TYPE = auto()
  PARENT_APP = auto()
  PARENT_APP_ENV = auto()
  NON_K8S_FILES_TO_RENDER = auto()
  EXCLUDE_RENDERING = auto()
  KUSTOMIZE_COMMON_DIRS = auto()
  APPLICATION_NAME = auto()

  @classmethod
  def get_values(cls):
      return list(map(lambda c: c.value, cls))


class Params:
  def __init__(self) -> None:
    self.app_type = ApplicationTypes.K8S
    self.parent_app = None
    self.parent_app_env = None
    self.non_k8s_files_to_render = []
    self.exclude_rendering = []
    self.kustomize_common_dirs = []
    self.application_name = ApplicationNameFormat.SHORT

  def populate_params(self, **kwargs) -> None:
    for param in kwargs:
      if param not in ParamNames.get_values():
        raise ConfigFileError(f'Unknown parameter `{param}` in Params')

    try:
      if 'app_type' in kwargs:
        kwargs['app_type'] = ApplicationTypes(kwargs['app_type'])
    except ValueError:
      raise ConfigFileError(f'Unknown application type `{kwargs["app_type"]}`. Valid types: {[t.value for t in ApplicationTypes]}')

    try:
      if 'application_name' in kwargs:
        kwargs['application_name'] = ApplicationNameFormat(kwargs['application_name'])
    except ValueError:
      raise ConfigFileError(f'Unknown application_name value `{kwargs["application_name"]}`. Valid values: {[f.value for f in ApplicationNameFormat]}')

    self.__dict__.update(kwargs)

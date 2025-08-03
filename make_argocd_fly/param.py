import logging

from make_argocd_fly.exception import ConfigFileError
from make_argocd_fly.const import ParamNames

log = logging.getLogger(__name__)


class Params:
  def __init__(self) -> None:
    self.parent_app = None
    self.parent_app_env = None
    self.non_k8s_files_to_render = []
    self.exclude_rendering = []

  def populate_params(self, **kwargs) -> None:
    for param in kwargs:
      if param not in ParamNames.get_names():
        log.error(f'Unknown parameter "{param}" in Params')
        raise ConfigFileError()

    self.__dict__.update(kwargs)

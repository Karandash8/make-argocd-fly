from dataclasses import dataclass
import logging

from make_argocd_fly.resource.type import ResourceType


log = logging.getLogger(__name__)


@dataclass
class OutputResource:
  app_name: str
  env_name: str
  resource_type: ResourceType
  data: str
  source_resource_path: str = ''
  output_resource_path: str = ''

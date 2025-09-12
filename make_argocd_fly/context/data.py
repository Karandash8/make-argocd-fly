from dataclasses import dataclass
from make_argocd_fly.resource.type import ResourceType


@dataclass
class OutputResource:
  resource_type: ResourceType
  data: str
  source: str
  output_path: str


@dataclass
class Content:
  resource_type: ResourceType
  data: str
  source: str


@dataclass
class Template:
  resource_type: ResourceType
  vars: dict
  data: str
  source: str

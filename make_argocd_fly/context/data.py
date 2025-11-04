from dataclasses import dataclass
from typing import Any
from make_argocd_fly.resource.viewer import ResourceType


@dataclass
class Template:
  resource_type: ResourceType
  vars: dict
  data: str
  source: str


@dataclass
class Content:
  resource_type: ResourceType
  data: str             # original text (for non-YAML this is the final data)
  source: str
  yaml_obj: Any = None  # Optional parsed YAML if conversion succeeded


@dataclass
class OutputResource:
  resource_type: ResourceType
  data: str             # original text (for non-YAML this is the final data)
  source: str
  output_path: str
  yaml_obj: Any = None  # Optional parsed YAML if conversion succeeded

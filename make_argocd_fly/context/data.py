from dataclasses import dataclass
from typing import Any
from make_argocd_fly.resource.viewer import ResourceType


@dataclass
class TemplatedResource:
  resource_type: ResourceType
  vars: dict
  data: str
  origin: str
  source_path: str | None = None


@dataclass
class Resource:
  resource_type: ResourceType
  data: str
  origin: str
  source_path: str | None = None
  yaml_obj: Any | None = None
  output_path: str | None = None

  def with_yaml(self, obj: Any) -> 'Resource':
    return Resource(
      resource_type=self.resource_type,
      data=self.data,
      origin=self.origin,
      source_path=self.source_path,
      yaml_obj=obj,
      output_path=self.output_path,
    )

  def with_output_path(self, output_path: str) -> 'Resource':
    return Resource(
      resource_type=self.resource_type,
      data=self.data,
      origin=self.origin,
      source_path=self.source_path,
      yaml_obj=self.yaml_obj,
      output_path=output_path,
    )

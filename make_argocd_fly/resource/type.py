from enum import Enum


class ResourceType(Enum):
  YAML = "yaml"
  JINJA2 = "jinja2"
  UNKNOWN = "unknown"
  DIRECTORY = "directory"
  DOES_NOT_EXIST = "does_not_exist"

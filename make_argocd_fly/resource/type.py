from enum import Enum


class ResourceType(Enum):
  YAML = "yaml"
  UNKNOWN = "unknown"
  DIRECTORY = "directory"
  DOES_NOT_EXIST = "does_not_exist"

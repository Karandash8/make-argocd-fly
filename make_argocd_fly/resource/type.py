from enum import StrEnum, auto


class ResourceType(StrEnum):
  YAML = auto()
  UNKNOWN = auto()
  DIRECTORY = auto()
  DOES_NOT_EXIST = auto()

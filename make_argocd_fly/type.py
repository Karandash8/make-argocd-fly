from enum import StrEnum, auto


class PipelineType(StrEnum):
  K8S_SIMPLE = auto()
  K8S_KUSTOMIZE = auto()
  K8S_HELMFILE = auto()
  K8S_APP_OF_APPS = auto()
  GENERIC = auto()


class WriterType(StrEnum):
  GENERIC = auto()
  K8S_YAML = auto()


class NamingPolicyType(StrEnum):
  SOURCE = auto()
  K8S = auto()

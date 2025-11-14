from abc import ABC, abstractmethod
import logging
import os
import yaml
from yaml import SafeDumper
from typing import Any, Final, NamedTuple

from make_argocd_fly.exception import InternalError, YamlObjectRequiredError
from make_argocd_fly.resource.viewer import ResourceType
from make_argocd_fly.param import ApplicationTypes

log = logging.getLogger(__name__)


class YamlDumper(SafeDumper):
  def increase_indent(self, flow=False, *args, **kwargs):
    return super().increase_indent(flow=flow, indentless=False)


def represent_str(dumper, data):
  '''
  configures pyyaml for dumping multiline strings
  Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
  '''
  if data.count('\n') > 0:
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
  '''
  configure pyyaml for dumping numbers that start with 0 as strings
  Ref: https://github.com/yaml/pyyaml/issues/98
  '''
  if data.startswith('0'):
    try:
      int(data[1:])
      return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='\'')
    except (SyntaxError, ValueError):
      pass

  return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='')


yaml.add_representer(str, represent_str, Dumper=YamlDumper)


class AbstractWriter(ABC):
  @abstractmethod
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None: ...


class GenericWriter(AbstractWriter):
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mode = 'wb' if isinstance(data, (bytes, bytearray)) else 'w'
    with open(output_path, mode) as f:
      f.write(data)


class YamlWriter(AbstractWriter):
  '''
  Strict YAML writer: requires a parsed YAML mapping (dict) as input.
  Never parses text here. If the pipeline doesn't provide yaml_obj, that's an error.
  '''
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not isinstance(data, dict):
      log.error('YamlWriter requires dict yaml_obj; got %s from %s', type(data).__name__, source)
      raise YamlObjectRequiredError()

    with open(output_path, 'w') as f:
      yaml.dump(data, f, Dumper=YamlDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                encoding='utf-8',
                explicit_start=True)


# Stateless singletons (safe to reuse across tasks)
GENERIC_WRITER: Final[AbstractWriter] = GenericWriter()
YAML_WRITER: Final[AbstractWriter] = YamlWriter()


class WriterPlan(NamedTuple):
  writer: AbstractWriter
  use_yaml_obj: bool  # True => pass resource.yaml_obj; False => pass resource.data


def plan_writer(app_type: ApplicationTypes,
                res_type: ResourceType,
                has_yaml_obj: bool) -> WriterPlan:
  '''
  Decide both the writer and which payload to pass.
  Rules:
    - GENERIC app type: always GenericWriter with raw data (never yaml_obj).
    - Non-GENERIC:
        * YAML => YamlWriter; payload is yaml_obj iff available; otherwise still YAML writer
          (caller will pass raw text only if you purposely allow parsing here; we forbid it).
        * Non-YAML => GenericWriter with raw data.
    - DIRECTORY / DOES_NOT_EXIST: invalid to write.
  '''
  if app_type == ApplicationTypes.GENERIC:
    return WriterPlan(GENERIC_WRITER, False)

  if res_type in (ResourceType.DIRECTORY, ResourceType.DOES_NOT_EXIST):
    log.error('Cannot write resource of type %s', res_type.name)
    raise InternalError()

  if res_type == ResourceType.YAML:
    return WriterPlan(YAML_WRITER, has_yaml_obj)

  return WriterPlan(GENERIC_WRITER, False)

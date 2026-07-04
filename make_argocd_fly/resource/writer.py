from abc import ABC, abstractmethod
import logging
import os
import yaml
from yaml import SafeDumper
from typing import Any, Final

from make_argocd_fly.exception import InternalError

log = logging.getLogger(__name__)


class YamlDumper(SafeDumper):
  def increase_indent(self, flow=False, *args, **kwargs):
    return super().increase_indent(flow=flow, indentless=False)


def represent_str(dumper, data):
  # configures pyyaml for dumping multiline strings
  # Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
  if data.count('\n') > 0:
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

  # configure pyyaml for dumping numbers that start with 0 as strings
  # Ref: https://github.com/yaml/pyyaml/issues/98
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
  def serialize(self, data: Any, env_name: str, app_name: str, origin: str) -> bytes: ...

  def write(self, output_path: str | os.PathLike[str], data: Any, env_name: str, app_name: str, origin: str) -> None:
    output_dir = os.path.dirname(os.fspath(output_path))
    if output_dir:
      os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'wb') as f:
      f.write(self.serialize(data, env_name, app_name, origin))


class GenericWriter(AbstractWriter):
  def serialize(self, data: Any, env_name: str, app_name: str, origin: str) -> bytes:
    if isinstance(data, bytes):
      return data
    if isinstance(data, (bytearray, memoryview)):
      return bytes(data)
    return str(data).encode('utf-8')


class YamlWriter(AbstractWriter):
  '''
  Strict YAML writer: requires a parsed YAML mapping (dict) as input.
  Never parses text here. If the pipeline doesn't provide yaml_obj, that's an error.
  '''
  def serialize(self, data: Any, env_name: str, app_name: str, origin: str) -> bytes:
    if not isinstance(data, dict):
      raise InternalError(f'YamlWriter requires dict yaml_obj; got {type(data).__name__} from {origin}')

    serialized = yaml.dump(data, Dumper=YamlDumper,
                           default_flow_style=False,
                           sort_keys=False,
                           allow_unicode=True,
                           encoding='utf-8',
                           explicit_start=True)
    if isinstance(serialized, bytes):
      return serialized
    return serialized.encode('utf-8')


# Stateless singletons (safe to reuse across tasks)
GENERIC_WRITER: Final[AbstractWriter] = GenericWriter()
YAML_WRITER: Final[AbstractWriter] = YamlWriter()

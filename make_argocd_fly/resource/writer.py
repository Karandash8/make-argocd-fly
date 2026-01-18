from abc import ABC, abstractmethod
import logging
import os
import yaml
from yaml import SafeDumper
from typing import Any, Final

from make_argocd_fly.exception import YamlObjectRequiredError

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
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, origin: str) -> None: ...


class GenericWriter(AbstractWriter):
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, origin: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mode = 'wb' if isinstance(data, (bytes, bytearray, memoryview)) else 'w'
    with open(output_path, mode) as f:
      if mode == 'w':
        f.write(str(data))
      else:
        f.write(data)


class YamlWriter(AbstractWriter):
  '''
  Strict YAML writer: requires a parsed YAML mapping (dict) as input.
  Never parses text here. If the pipeline doesn't provide yaml_obj, that's an error.
  '''
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, origin: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not isinstance(data, dict):
      log.error('YamlWriter requires dict yaml_obj; got %s from %s', type(data).__name__, origin)
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

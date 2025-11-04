from abc import ABC, abstractmethod
import logging
import os
import yaml
import yaml.composer
import yaml.parser
import yaml.scanner
import yaml.constructor
import asyncio
from yaml import SafeDumper
from typing import Protocol, Any
from dataclasses import dataclass

try:
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  from yaml import SafeLoader

from make_argocd_fly.exception import InternalError, YamlError
from make_argocd_fly.resource.viewer import ResourceType
from make_argocd_fly.param import ApplicationTypes

log = logging.getLogger(__name__)


class YamlLoader(SafeLoader):
  pass


class YamlDumper(SafeDumper):
  def increase_indent(self, flow=False, *args, **kwargs):
    return super().increase_indent(flow=flow, indentless=False)


def represent_str(dumper, data):
  """configures pyyaml for dumping multiline strings
  Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data"""
  if data.count('\n') > 0:
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
  """configure pyyaml for dumping numbers that start with 0 as strings
  Ref: https://github.com/yaml/pyyaml/issues/98"""
  if data.startswith('0'):
    try:
      int(data[1:])
      return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='\'')
    except (SyntaxError, ValueError):
      pass

  return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='')


yaml.add_representer(str, represent_str, Dumper=YamlDumper)


class AsyncWriterProto(Protocol):
  async def write_async(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None: ...


class AbstractWriter(ABC):
  @abstractmethod
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    pass


class GenericWriter(AbstractWriter):
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if isinstance(data, (bytes, bytearray, memoryview)):
      with open(output_path, 'wb') as f:
        f.write(data)
    else:
      with open(output_path, 'w', encoding='utf-8') as f:
        f.write(str(data))


class YamlWriter(AbstractWriter):
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if isinstance(data, (dict, list)):
      yaml_resource = data
    else:
      try:
        yaml_resource = yaml.load(data, Loader=YamlLoader)
      except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError, yaml.constructor.ConstructorError):
        log.error(f'Error building YAML from source `{source}` for resource {app_name} in environment {env_name}')
        log.debug(f'YAML content:\n{data}')
        raise YamlError(app_name, env_name) from None

    with open(output_path, 'w') as f:
      yaml.dump(yaml_resource, f, Dumper=YamlDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                encoding='utf-8',
                explicit_start=True)


@dataclass
class SyncToAsyncWriter(AsyncWriterProto):
  sync_writer: AbstractWriter

  async def write_async(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    await asyncio.to_thread(self.sync_writer.write, output_path, data, env_name, app_name, source)


def writer_factory(app_type: ApplicationTypes, res_type: ResourceType) -> AbstractWriter:
  if app_type == ApplicationTypes.GENERIC:
    return GenericWriter()
  else:
    if res_type == ResourceType.DIRECTORY or res_type == ResourceType.DOES_NOT_EXIST:
      log.error(f'Cannot write resource of type {res_type.name}')
      raise InternalError()

    if res_type == ResourceType.YAML:
      return YamlWriter()
    else:
      return GenericWriter()

from abc import ABC, abstractmethod
import logging
import os
import asyncio
import yaml
import yaml.composer
import yaml.parser
import yaml.scanner
from yaml import SafeDumper
from typing import Any

try:
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  from yaml import SafeLoader

from make_argocd_fly.exception import InternalError, YamlError
from make_argocd_fly.resource.type import ResourceType
from make_argocd_fly.context.data import OutputResource

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


class AbstractWriter(ABC):
  @abstractmethod
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    pass


class GenericWriter(AbstractWriter):
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
      f.write(data)


class YamlWriter(AbstractWriter):
  def write(self, output_path: str, data: Any, env_name: str, app_name: str, source: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

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


def writer_factory(type: ResourceType) -> AbstractWriter:
  if type == ResourceType.DIRECTORY or type == ResourceType.DOES_NOT_EXIST:
    log.error(f'Cannot write resource of type {type.name}')
    raise InternalError()

  if type == ResourceType.YAML:
    return YamlWriter()
  else:
    return GenericWriter()


class ResourcePersistence:
  def __init__(self, output_dir_abs_path: str, env_name: str, app_name: str) -> None:
    self.output_dir_abs_path = output_dir_abs_path
    self.env_name = env_name
    self.app_name = app_name
    self.resources = {}

  def store_resource(self, resource: OutputResource) -> None:
    if not resource.output_path:
      log.error('Parameter `output_path` is not set for resource')
      raise InternalError()

    if resource.output_path in self.resources:
      log.error(f'Resource ({resource.output_path}) already exists')
      raise InternalError()

    self.resources[resource.output_path] = resource

  async def _write_resource(self, resource: OutputResource) -> None:
    writer = writer_factory(resource.resource_type)
    writer.write(os.path.join(self.output_dir_abs_path, resource.output_path), resource.data, self.env_name, self.app_name, resource.source)

  async def write_resources(self) -> None:
    try:
      await asyncio.gather(
        *[asyncio.create_task(self._write_resource(resource)) for resource in self.resources.values()]
      )
    except Exception as e:
      for task in asyncio.all_tasks():
        task.cancel()
      raise e

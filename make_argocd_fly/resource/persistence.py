from abc import ABC, abstractmethod
import logging
import os
import asyncio
import yaml
from typing import Any
from yaml import SafeDumper

from make_argocd_fly.exception import InternalError
from make_argocd_fly.resource.type import ResourceType

log = logging.getLogger(__name__)


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
  def write(self, path: str, data: Any) -> None:
    pass


class GenericWriter(AbstractWriter):
  def write(self, path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, 'w') as f:
      f.write(data)


class YamlWriter(AbstractWriter):
  def write(self, path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, 'w') as f:
      yaml.dump(data, f, Dumper=YamlDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                encoding='utf-8',
                explicit_start=True)


def writer_factory(type: ResourceType) -> AbstractWriter:
  if type == ResourceType.DIRECTORY or type == ResourceType.DOES_NOT_EXIST:
    log.error(f'Cannot write resource of type {type}')
    raise InternalError()

  if type == ResourceType.YAML:
    return YamlWriter()
  else:
    return GenericWriter()


class ResourcePersistence:
  def __init__(self, output_dir_abs_path: str) -> None:
    self.output_dir_abs_path = output_dir_abs_path
    self.resources = {}

  def store_resource(self, path: str, data_type: ResourceType, data: Any) -> None:
    if not path:
      log.error('Parameter `path` is undefined')
      raise InternalError()

    if path in self.resources:
      log.error(f'Resource ({path}) already exists')
      raise InternalError()

    self.resources[path] = (data_type, data)

  async def _write_resource(self, file_path: str, data_type: ResourceType, data: Any) -> None:
    writer = writer_factory(data_type)
    writer.write(os.path.join(self.output_dir_abs_path, file_path), data)

  async def write_resources(self) -> None:
    try:
      await asyncio.gather(
        *[asyncio.create_task(self._write_resource(file_path, data_type, data)) for file_path, (data_type, data) in self.resources.items()]
      )
    except Exception as e:
      for task in asyncio.all_tasks():
        task.cancel()
      raise e

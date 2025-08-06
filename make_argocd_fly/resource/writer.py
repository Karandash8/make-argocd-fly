import logging
import os
import asyncio
import yaml
from yaml import SafeDumper

from make_argocd_fly.exception import InternalError

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


class ResourceWriter:
  def __init__(self, output_dir_abs_path: str) -> None:
    self.output_dir_abs_path = output_dir_abs_path
    self.resources = {}

  def store_resource(self, file_path: str, yaml_object: str) -> None:
    if not file_path:
      log.error('Parameter `file_path` is undefined')
      raise InternalError()

    if file_path in self.resources:
      log.error(f'Resource ({file_path}) already exists')
      raise InternalError()

    self.resources[file_path] = yaml_object

  async def _write_resource(self, file_path: str, yaml_object: str) -> None:
    path = os.path.join(self.output_dir_abs_path, os.path.dirname(file_path))
    os.makedirs(path, exist_ok=True)

    with open(os.path.join(self.output_dir_abs_path, file_path), 'w') as f:
      yaml.dump(yaml_object, f, Dumper=YamlDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                encoding='utf-8',
                explicit_start=True)

  async def write_resources(self) -> None:
    try:
      await asyncio.gather(
        *[asyncio.create_task(self._write_resource(file_path, yaml_object)) for file_path, yaml_object in self.resources.items()]
      )
    except Exception as e:
      for task in asyncio.all_tasks():
        task.cancel()
      raise e

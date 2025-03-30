import logging
import os
import re
import asyncio
import yaml
import yaml.composer
import yaml.parser
from yaml import SafeDumper

from make_argocd_fly.exceptions import MissingApplicationDirectoryError, InternalError

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


class ResourceViewer:
  def __init__(self, root_element_abs_path: str, element_rel_path: str = '.', is_dir: bool = True) -> None:
    self.root_element_abs_path = root_element_abs_path
    self.element_rel_path = os.path.normpath(element_rel_path)
    self.is_dir = is_dir

    if self.element_rel_path == '.':
      self.name = os.path.basename(self.root_element_abs_path)
    else:
      self.name = os.path.basename(self.element_rel_path)

    self.content = None
    self.children = []

  def build(self) -> None:
    if not os.path.exists(self.root_element_abs_path):
      raise MissingApplicationDirectoryError(self.root_element_abs_path)

    path = os.path.join(self.root_element_abs_path, self.element_rel_path)
    if not os.path.exists(path):
      log.error('Path does not exist {}'.format(path))
      raise InternalError

    if self.is_dir:
      for child_name in os.listdir(path):
        child_rel_path = os.path.join(self.element_rel_path, child_name)
        child = ResourceViewer(self.root_element_abs_path, child_rel_path, os.path.isdir(os.path.join(self.root_element_abs_path, child_rel_path)))
        child.build()
        self.children.append(child)
    else:
      try:
        with open(path) as f:
          self.content = ''.join(f.readlines())
      except UnicodeDecodeError:
        log.warning('File is not a text file {}'.format(path))

    log.debug('Created element ({})'.format(self))

  def _get_child(self, name: str) -> 'ResourceViewer':
    for child in self.children:
      if child.name == name:
        return child

    return None

  def get_element(self, path: str) -> 'ResourceViewer':
    path_split = (os.path.normpath(path)).split('/')
    if len(path_split) > 1:
      child = self._get_child(path_split[0])
      if child:
        return child.get_element('/'.join(path_split[1:]))
    elif len(path_split) == 1:
      return self._get_child(path_split[0])

    return None

  def get_children(self) -> list:
    return self.children

  # if `search_subdirs` is a list of subdirs, then only those subdirs will be searched
  def get_files_children(self, name_pattern: str, search_subdirs: list = None) -> list:
    files = []
    for child in self.children:
      if not child.is_dir and re.search(name_pattern, child.name):
        files.append(child)
      else:
        if not search_subdirs:
          files.extend(child.get_files_children(name_pattern))
        elif child.name in search_subdirs:
          files.extend(child.get_files_children(name_pattern))

    return files

  def get_dirs_children(self, depth: int = 1) -> list:
    dirs = []
    for child in self.children:
      if child.is_dir:
        dirs.append(child)
        if depth > 1:
          dirs.extend(child.get_dirs_children(depth - 1))

    return dirs

  def __str__(self) -> str:
    return 'root_path: {}, element_rel_path: {}, is_dir: {}'.format(self.root_element_abs_path, self.element_rel_path, self.is_dir)


class ResourceWriter:
  def __init__(self, output_dir_abs_path: str) -> None:
    self.output_dir_abs_path = output_dir_abs_path
    self.resources = {}

  def store_resource(self, file_path: str, yaml_object: str) -> None:
    if not file_path:
      log.error('Parameter `file_path` is undefined')
      raise InternalError

    if file_path in self.resources:
      log.error('Resource ({}) already exists'.format(file_path))
      raise InternalError

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

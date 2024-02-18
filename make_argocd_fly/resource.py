import logging
import os
import re
import asyncio
import yaml
try:
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  from yaml import SafeLoader

log = logging.getLogger(__name__)


class SafeDumper(yaml.SafeDumper):
  def increase_indent(self, flow=False, *args, **kwargs):
    return super().increase_indent(flow=flow, indentless=False)


def str_presenter(dumper, data):
    """configures yaml for dumping multiline strings
    Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data"""
    if data.count('\n') > 0:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter, Dumper=SafeDumper)


class ResourceViewer:
  def __init__(self, root_element_abs_path: str, element_rel_path: str = '.', is_dir: bool = True) -> None:
    if not os.path.exists(root_element_abs_path):
      log.error('Path does not exist {}'.format(root_element_abs_path))
      raise Exception

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
    path = os.path.join(self.root_element_abs_path, self.element_rel_path)
    if not os.path.exists(path):
      log.error('Path does not exist {}'.format(path))
      raise Exception

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

  def store_resource(self, file_path: str, resource_yml: str) -> None:
    if not file_path:
      log.error('Parameter `file_path` is undefined')
      raise Exception

    if file_path in self.resources:
      log.error('Resource ({}) already exists'.format(file_path))
      raise Exception

    self.resources[file_path] = resource_yml

  async def _write_resource(self, file_path: str, resource_yml: str) -> None:
    path = os.path.join(self.output_dir_abs_path, os.path.dirname(file_path))
    os.makedirs(path, exist_ok=True)

    with open(os.path.join(self.output_dir_abs_path, file_path), 'w') as f:
      f.write(resource_yml)
    yaml_obj = yaml.load(resource_yml, Loader=SafeLoader)
    with open(os.path.join(self.output_dir_abs_path, file_path), 'w') as f:
      yaml.dump(yaml_obj, f, Dumper=SafeDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                encoding='utf-8',
                explicit_start=True)

  async def write_resources(self) -> None:
    await asyncio.gather(
      *[self._write_resource(file_path, resource_yml) for file_path, resource_yml in self.resources.items()]
    )

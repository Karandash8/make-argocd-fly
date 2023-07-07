import logging
import os
import re

from make_argocd_fly.utils import resource_parser, multi_resource_parser, extract_dir_rel_path
from make_argocd_fly.renderer import AbstractRenderer, JinjaRenderer

log = logging.getLogger(__name__)


class ResourceViewer:
  def __init__(self, root_element_abs_path: str, tmp_dir_abs_path: str, renderer: AbstractRenderer, template_vars: dict) -> None:
    if not os.path.exists(root_element_abs_path):
      log.error('Path does not exist {}'.format(root_element_abs_path))
      raise Exception

    self.root_element_abs_path = root_element_abs_path
    self.tmp_dir_abs_path = tmp_dir_abs_path
    self.renderer = renderer
    self.template_vars = template_vars
    self.element_rel_path = None
    self.name = None
    self.is_dir = None
    self.content = None
    self.children = []

  def build(self, element_rel_path:str, is_root_element: bool = False) -> None:
    self.element_rel_path = element_rel_path
    if is_root_element:
      self.name = os.path.basename(self.root_element_abs_path)
    else:
      self.name = os.path.basename(element_rel_path)

    path = os.path.join(self.root_element_abs_path, element_rel_path)
    self.is_dir = os.path.isdir(path)
    if self.is_dir:
      for child_name in os.listdir(path):
        child = ResourceViewer(self.root_element_abs_path, self.tmp_dir_abs_path, self.renderer, self.template_vars)
        child.build(os.path.join(element_rel_path, child_name))
        self.children.append(child)
    else:
      with open(path) as f:
        content = ''.join(f.readlines())

        if self.name.endswith('.j2'):
          self.content = self.renderer.render(content, self.template_vars)
          self.name = self.name[:-3]
        else:
          self.content = content

    log.debug('Created element ({})'.format(self))

  def get_child(self, name: str) -> 'ResourceViewer':
    for child in self.children:
      if child.name == name:
        return child

    return None

  def get_children(self) -> list:
    return self.children

  def get_files_children(self, name_pattern: str) -> list:
    files = []
    for child in self.children:
      if not child.is_dir and re.search(name_pattern, child.name):
        files.append(child)
      else:
        files.extend(child.get_files_children(name_pattern))

    return files

  def get_dirs_children(self, depth:int = 1) -> list:
    dirs = []
    for child in self.children:
      if child.is_dir:
        dirs.append(child)
        if depth > 1:
          dirs.extend(child.get_dirs_children(depth - 1))

    return dirs

  def __str__(self) -> str:
    return 'name: {}, is_dir: {}, element_rel_path: {}'.format(self.name, self.is_dir, self.element_rel_path)


def build_resource_viewer(root_element_abs_path: str, tmp_dir_abs_path: str, template_vars: dict, filter: str = None) -> ResourceViewer:
  source_viewer = ResourceViewer(root_element_abs_path, tmp_dir_abs_path, JinjaRenderer(), template_vars)
  source_viewer.build('.', is_root_element=True)

  return source_viewer


class ResourceWriter:
  def __init__(self, output_dir_abs_path: str) -> None:
    self.output_dir_abs_path = output_dir_abs_path
    self.resources = {}

  def store_resource(self, dir_rel_path: str, resource_kind: str, resource_name: str, resource_yml: str) -> None:
    self.resources[(dir_rel_path, resource_kind, resource_name)] = resource_yml

  def write_resources(self) -> None:
    for (dir_rel_path, resource_kind, _), resource_yml in self.resources.items():
      self._write_file_resource(dir_rel_path, resource_kind + '.yml', resource_yml)

  def _write_file_resource(self, dir_rel_path: str, filename: str, resource_yml: str) -> None:
    path = os.path.join(self.output_dir_abs_path, dir_rel_path)
    os.makedirs(path, exist_ok=True)

    if not os.path.exists(os.path.join(path, filename.lower())):
      with open(os.path.join(path, filename.lower()), 'w') as f:
        f.write(resource_yml)
        f.write('\n')
    else:
      with open(os.path.join(path, filename.lower()), 'a') as f:
        f.write('---\n')
        f.write(resource_yml)
        f.write('\n')


def build_resource_writer(output_dir_abs_path: str, filter: str = None) -> ResourceWriter:
  return ResourceWriter(output_dir_abs_path)

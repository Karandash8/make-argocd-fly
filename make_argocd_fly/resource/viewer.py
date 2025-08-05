import logging
import os
import re
from enum import Enum
from typing import Optional, Generator

from make_argocd_fly.exception import ResourceViewerIsFake

log = logging.getLogger(__name__)


class ResourceType(Enum):
  YAML = "yaml"
  JINJA2 = "jinja2"
  UNKNOWN = "unknown"
  DIRECTORY = "directory"
  DOES_NOT_EXIST = "does_not_exist"


EXTENSION_MAP = {
  '.yml': ResourceType.YAML,
  '.yaml': ResourceType.YAML,
  '.j2': ResourceType.JINJA2,
}


def get_resource_type(path: str) -> ResourceType:
  if not os.path.exists(path):
    return ResourceType.DOES_NOT_EXIST

  if os.path.isdir(path):
    return ResourceType.DIRECTORY

  _, ext = os.path.splitext(path)

  return EXTENSION_MAP.get(ext, ResourceType.UNKNOWN)


class ResourceViewer:
  def __init__(self, root_element_abs_path: str, element_rel_path: str = '.') -> None:
    self.root_element_abs_path = root_element_abs_path
    self.element_rel_path = os.path.normpath(element_rel_path)

    if self.element_rel_path == '.':
      self.name = os.path.basename(self.root_element_abs_path)
    else:
      self.name = os.path.basename(self.element_rel_path)

    self.resource_type = None
    self.content = ''
    self.children = []
    self.children_resources = {}

    self._build()

  def _build(self) -> None:
    path = os.path.join(self.root_element_abs_path, self.element_rel_path)
    self.resource_type = get_resource_type(path)

    if self.resource_type == ResourceType.DIRECTORY:
      for child_name in os.listdir(path):
        child_rel_path = os.path.join(self.element_rel_path, child_name)
        child = ResourceViewer(self.root_element_abs_path, child_rel_path)
        self.children.append(child)

        self.children_resources[os.path.normpath(child_rel_path)] = child
    elif self.resource_type != ResourceType.DOES_NOT_EXIST:
      try:
        with open(path) as f:
          self.content = ''.join(f.readlines())
      except UnicodeDecodeError:
        log.warning(f'File {path} is not a text file, cannot read content')

    log.debug(f'Created element ({self})')

  def _get_child(self, name: str) -> Optional['ResourceViewer']:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    for child in self.children:
      if child.name == name:
        return child

    return None

  def get_element(self, path: str) -> Optional['ResourceViewer']:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    path_split = (os.path.normpath(path)).split('/')
    if len(path_split) > 1:
      child = self._get_child(path_split[0])
      if child:
        return child.get_element('/'.join(path_split[1:]))
    elif len(path_split) == 1:
      return self._get_child(path_split[0])

    return None

  def get_children(self) -> list:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    return self.children

  # if `search_subdirs` is a list of subdirs, then only those subdirs will be searched
  def get_files_children(self, name_pattern: str, search_subdirs: list | None = None) -> list:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    files = []
    for child in self.children:
      if child.resource_type != ResourceType.DIRECTORY and child.resource_type != ResourceType.DOES_NOT_EXIST and re.search(name_pattern, child.name):
        files.append(child)
      else:
        if not search_subdirs:
          files.extend(child.get_files_children(name_pattern))
        elif child.name in search_subdirs:
          files.extend(child.get_files_children(name_pattern))

    return files

  def get_dirs_children(self, depth: int = 1) -> list:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    dirs = []
    for child in self.children:
      if child.resource_type == ResourceType.DIRECTORY:
        dirs.append(child)
        if depth > 1:
          dirs.extend(child.get_dirs_children(depth - 1))

    return dirs

  def _get_subresources(self,
                        resource_types: list[ResourceType] | None = None,
                        depth: int = -1) -> dict[str, 'ResourceViewer']:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    subresources = {}
    for rel_path, subresource in self.children_resources.items():
      if (resource_types is None or subresource.resource_type in resource_types) and (depth == -1 or depth > 0):
        subresources[rel_path] = subresource

      if subresource.resource_type == ResourceType.DIRECTORY and (depth == -1 or depth > 0):
        subresources |= subresource._get_subresources(resource_types, depth - 1 if depth > 0 else -1)

    return subresources

  def search_subresources(self,
                          resource_types: list[ResourceType] | None = None,
                          name_pattern: str = r'.*',
                          search_subdirs: list[str] | None = None,
                          depth: int = -1) -> Generator['ResourceViewer', None, None]:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    if search_subdirs is not None:
      all_subdirs = self._get_subresources(resource_types=[ResourceType.DIRECTORY])

      for subdir in search_subdirs:
        if subdir in all_subdirs:
          yield from all_subdirs[subdir].search_subresources(resource_types=resource_types,
                                                             name_pattern=name_pattern,
                                                             depth=depth)
    else:
      for subresource in self.children_resources.values():
        if ((resource_types is None or subresource.resource_type in resource_types) and
            re.search(name_pattern, subresource.name) and
            (depth == -1 or depth > 0)):
          yield subresource

        if subresource.resource_type == ResourceType.DIRECTORY and (depth == -1 or depth > 0):
          yield from subresource.search_subresources(resource_types=resource_types,
                                                     name_pattern=name_pattern,
                                                     depth=depth - 1 if depth > 0 else -1)

  def __str__(self) -> str:
    return f'root_path: {self.root_element_abs_path}, element_rel_path: {self.element_rel_path}, resource_type: {self.resource_type}'

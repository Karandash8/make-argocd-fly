import logging
import os
import re
from typing import Generator
from enum import StrEnum, auto

from make_argocd_fly.exception import ResourceViewerIsFake

log = logging.getLogger(__name__)


class ResourceType(StrEnum):
  YAML = auto()
  UNKNOWN = auto()
  DIRECTORY = auto()
  DOES_NOT_EXIST = auto()


EXTENSION_MAP = {
  '.yml': ResourceType.YAML,
  '.yaml': ResourceType.YAML,
}

TEMPLATE_EXTENSIONS = {'.j2'}


def get_resource_params(path: str) -> tuple[ResourceType, bool]:
  template = False

  if not os.path.exists(path):
    return ResourceType.DOES_NOT_EXIST, template
  if os.path.isdir(path):
    return ResourceType.DIRECTORY, template

  path_wo_ext, ext = os.path.splitext(path)
  if ext in TEMPLATE_EXTENSIONS:
    template = True
    _, ext = os.path.splitext(path_wo_ext)

  return EXTENSION_MAP.get(ext, ResourceType.UNKNOWN), template


class ResourceViewer:
  def __init__(self, root_element_abs_path: str, element_rel_path: str = '.') -> None:
    self.root_element_abs_path = root_element_abs_path
    self.element_rel_path = os.path.normpath(element_rel_path)

    if self.element_rel_path == '.':
      self.name = os.path.basename(self.root_element_abs_path)
    else:
      self.name = os.path.basename(self.element_rel_path)

    self.resource_type = ResourceType.DOES_NOT_EXIST
    self.template = False
    self.content = ''
    self.subresources = {}

    self._build()

  def _build(self) -> None:
    path = os.path.join(self.root_element_abs_path, self.element_rel_path)
    self.resource_type, self.template = get_resource_params(path)

    if self.resource_type == ResourceType.DIRECTORY:
      for child_name in os.listdir(path):
        child_rel_path = os.path.join(self.element_rel_path, child_name)
        self.subresources[os.path.normpath(child_rel_path)] = ResourceViewer(self.root_element_abs_path, child_rel_path)
    elif self.resource_type != ResourceType.DOES_NOT_EXIST:
      try:
        with open(path) as f:
          self.content = ''.join(f.readlines())
      except UnicodeDecodeError:
        log.warning(f'File {path} is not a text file, cannot read content')

    log.debug(f'Created element ({self})')

  def _get_subresources(self,
                        resource_types: list[ResourceType] | None = None,
                        template: bool | None = None,
                        depth: int = -1) -> dict[str, 'ResourceViewer']:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    subresources = {}
    for rel_path, subresource in self.subresources.items():
      if ((resource_types is None or subresource.resource_type in resource_types) and
          (template is None or subresource.template == template) and
          (depth == -1 or depth > 0)):
        subresources[rel_path] = subresource

      if subresource.resource_type == ResourceType.DIRECTORY and (depth == -1 or depth > 0):
        subresources |= subresource._get_subresources(resource_types, template, depth - 1 if depth > 0 else -1)

    return subresources

  def search_subresources(self,
                          resource_types: list[ResourceType] | None = None,
                          template: bool | None = None,
                          name_pattern: str = r'.*',
                          search_subdirs: list[str] | None = None,
                          depth: int = -1) -> Generator['ResourceViewer', None, None]:
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise ResourceViewerIsFake(os.path.join(self.root_element_abs_path, self.element_rel_path))

    if search_subdirs is not None:
      all_subdirs = self._get_subresources(resource_types=[ResourceType.DIRECTORY]) | {'.': self}

      for subdir in search_subdirs:
        if subdir in all_subdirs:
          yield from all_subdirs[subdir].search_subresources(resource_types=resource_types,
                                                             template=template,
                                                             name_pattern=name_pattern,
                                                             depth=depth)
    else:
      for subresource in self.subresources.values():
        if ((resource_types is None or subresource.resource_type in resource_types) and
            (template is None or subresource.template == template) and
            re.search(name_pattern, subresource.name) and
            (depth == -1 or depth > 0)):
          yield subresource

        if subresource.resource_type == ResourceType.DIRECTORY and (depth == -1 or depth > 0):
          yield from subresource.search_subresources(resource_types=resource_types,
                                                     template=template,
                                                     name_pattern=name_pattern,
                                                     depth=depth - 1 if depth > 0 else -1)

  def __str__(self) -> str:
    return f'root_path: {self.root_element_abs_path}, element_rel_path: {self.element_rel_path}, resource_type: {self.resource_type}'

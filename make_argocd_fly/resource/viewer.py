import logging
import os
import re
from typing import Generator, Iterable
from enum import StrEnum, auto

from make_argocd_fly.exception import PathDoesNotExistError
from make_argocd_fly.util import is_match

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


def _get_resource_params(path: str) -> tuple[ResourceType, bool]:
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
  def __init__(self, path: str) -> None:
    self.path = os.path.normpath(path)
    self.name = os.path.basename(path)

    self.resource_type = ResourceType.DOES_NOT_EXIST
    self.template = False
    self.content = ''
    self.children = {}

    self._build()

  def _build(self) -> None:
    self.resource_type, self.template = _get_resource_params(self.path)
    if self.resource_type == ResourceType.DIRECTORY:
      for child_name in os.listdir(self.path):
        self.children[child_name] = ResourceViewer(os.path.join(self.path, child_name))
        self.children[child_name].children['..'] = self
    elif self.resource_type != ResourceType.DOES_NOT_EXIST:
      try:
        with open(self.path) as f:
          self.content = ''.join(f.readlines())
      except UnicodeDecodeError:
        log.warning(f'File {self.path} is not a text file, cannot read content')

    log.debug(f'Created element ({self})')

  def _go_to(self, path: str) -> 'ResourceViewer':
    parts = os.path.normpath(path).split(os.sep)
    current = self

    for part in parts:
      if part not in current.children:
        raise PathDoesNotExistError(path)

      current = current.children[part]

    return current

  def _iter_children(self):
    """Yield (name, node) for children excluding the parent backlink '..'."""
    for name, node in self.children.items():
      if name == '..':
        continue
      yield name, node

  def _search_subresources(self,
                           resource_types: list[ResourceType] | None = None,
                           template: bool | None = None,
                           name_pattern: str = r'.*',
                           search_subdirs: list[str] | None = None,
                           depth: int = -1) -> Generator['ResourceViewer', None, None]:
    """
    Yield children matching filters. If search_subdirs is provided, treat each
    item as a path relative to `self` ('.' allowed). Depth: -1 means unlimited.
    """
    if self.resource_type == ResourceType.DOES_NOT_EXIST:
      raise PathDoesNotExistError(self.path)

    # If specific subdirs requested, delegate to each target and stop here.
    if search_subdirs is not None:
      for subdir in search_subdirs:
        try:
          target = self if subdir == '.' else self._go_to(subdir)
        except PathDoesNotExistError:
          continue
        # Recurse from that subdir with the same filters, but without search_subdirs
        yield from target._search_subresources(resource_types=resource_types,
                                               template=template,
                                               name_pattern=name_pattern,
                                               search_subdirs=None,
                                               depth=depth)
      return

    regex = re.compile(name_pattern)

    for _, child in self._iter_children():
        # Apply filters for the child itself
        if ((resource_types is None or child.resource_type in resource_types) and
            (template is None or child.template == template) and
            regex.search(child.name) and
            (depth == -1 or depth > 0)):
          yield child

        # Recurse into directories if depth allows
        if child.resource_type == ResourceType.DIRECTORY and (depth == -1 or depth > 0):
          next_depth = (depth - 1) if depth > 0 else -1
          yield from child._search_subresources(resource_types=resource_types,
                                                template=template,
                                                name_pattern=name_pattern,
                                                search_subdirs=None,
                                                depth=next_depth)

  def scoped(self) -> "ScopedViewer":
    return ScopedViewer(self, base_path=self.path)

  def __str__(self) -> str:
    return f'{self.__class__.__name__}({self.path}) of type {self.resource_type}'


class ScopedViewer:
  """
  Immutable, lightweight view over a ResourceViewer subtree.
  rel_path is computed relative to base_path, not the global source root.
  """
  __slots__ = ("_node", "_base_path")

  def __init__(self, node: "ResourceViewer", base_path: str | None = None) -> None:
    self._node = node
    self._base_path = os.path.normpath(base_path or node.path)

  @property
  def path(self) -> str:
    return self._node.path

  @property
  def name(self) -> str:
    return self._node.name

  @property
  def resource_type(self) -> ResourceType:
    return self._node.resource_type

  @property
  def template(self) -> bool:
    return self._node.template

  @property
  def content(self) -> str:
    return self._node.content

  @property
  def rel_path(self) -> str:
    rel = os.path.relpath(self._node.path, self._base_path)
    return "." if rel == "." else os.path.normpath(rel)

  def go_to(self, path: str, rebase: bool = True) -> "ScopedViewer":
    nxt = self._node._go_to(path)
    if rebase:
      # Navigate and make the target the new '.'
      return ScopedViewer(nxt, base_path=nxt.path)
    else:
      # Keep the original base path
      return ScopedViewer(nxt, base_path=self._base_path)

  def search_subresources(self,
                          resource_types: list["ResourceType"] | None = None,
                          template: bool | None = None,
                          name_pattern: str = r'.*',
                          search_subdirs: list[str] | None = None,
                          depth: int = -1,
                          excludes: Iterable[str] | None = None,
                          includes: Iterable[str] | None = None):
    """
    Delegate to the underlying node but re-wrap yielded children in this scope.
    `search_subdirs` remain relative to this scope (same as underlying semantics).
    `excludes` / `includes` are POSIX-like relative patterns (prefix or glob),
    matched against this scope's `rel_path`.
    """

    exclude_patterns = list(excludes or [])
    include_patterns = list(includes or [])

    for child in self._node._search_subresources(resource_types=resource_types,
                                                 template=template,
                                                 name_pattern=name_pattern,
                                                 search_subdirs=search_subdirs,
                                                 depth=depth):
      scoped = ScopedViewer(child, base_path=self._base_path)

      if exclude_patterns and is_match(scoped.rel_path, exclude_patterns):
        log.debug('Excluding %s', scoped.rel_path)
        continue

      if include_patterns and not is_match(scoped.rel_path, include_patterns):
        continue

      yield scoped

  def iter_children(self):
    for _, child in self._node._iter_children():
      yield ScopedViewer(child, base_path=self._base_path)

  def child(self, name: str) -> "ScopedViewer":
    return ScopedViewer(self._node._go_to(name), base_path=self._base_path)

  def exists(self, path: str) -> bool:
    try:
      _ = self._node._go_to(os.path.normpath(path))
      return True
    except PathDoesNotExistError:
      return False

  def __str__(self) -> str:
    return f"{self.__class__.__name__}({self.path}, base={self._base_path})"


def build_scoped_viewer(path: str) -> ScopedViewer:
    return ResourceViewer(path).scoped()

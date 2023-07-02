import logging
import os
import re

log = logging.getLogger(__name__)


class SourceViewer:
  def __init__(self, source_dir: str) -> None:
    if not os.path.exists(source_dir):
      log.error('Path does not exist {}'.format(source_dir))
      raise Exception

    self.source_dir = source_dir
    self.relative_path = None
    self.name = None
    self.is_dir = None
    self.content = None
    self.children = []

  def build(self, relative_path:str, is_source_dir: bool = True) -> None:
    self.relative_path = relative_path
    if is_source_dir:
      self.name = os.path.basename(self.source_dir)
    else:
      self.name = os.path.basename(relative_path)

    path = os.path.join(self.source_dir, relative_path)
    self.is_dir = os.path.isdir(path)
    if self.is_dir:
      for child_name in os.listdir(path):
        child = SourceViewer(self.source_dir)
        child.build(os.path.join(relative_path, child_name), is_source_dir=False)
        self.children.append(child)
    else:
      with open(path) as f:
        self.content = f.readlines()

    log.debug('Created element ({})'.format(self))

  def list_children_names(self) -> list:
    return [child.name for child in self.children]

  def is_a_child(self, name: str) -> bool:
    return name in self.list_children_names()

  def get_child(self, name: str) -> 'SourceViewer':
    for child in self.children:
      if child.name == name:
        return child

    return None

  def list_children(self) -> list:
    return self.children

  def list_files_children(self, name_pattern: str) -> list:
    files = []
    for child in self.children:
      if not child.is_dir and re.search(name_pattern, child.name):
        files.append(child)
      else:
        files.extend(child.list_files_children(name_pattern))

    return files

  def list_dirs_children(self, depth:int = 1) -> list:
    dirs = []
    for child in self.children:
      if child.is_dir:
        dirs.append(child)
        if depth > 1:
          dirs.extend(child.list_dirs_children(depth - 1))

    return dirs

  def __str__(self) -> str:
    return 'name: {}, is_dir: {}, relative_path: {}'.format(self.name, self.is_dir, self.relative_path)

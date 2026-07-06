import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileRecord:
  rel_path: str
  abs_path: str
  size: int
  mtime_ns: int


@dataclass
class OutputInventory:
  files: dict[str, FileRecord] = field(default_factory=dict)


def _normalize_rel_path(path: str) -> str:
  return os.path.normpath(path).replace(os.sep, '/')


def _scan_dir(output_dir: str, current_dir: str, files: dict[str, FileRecord]) -> None:
  with os.scandir(current_dir) as entries:
    for entry in entries:
      if entry.is_dir(follow_symlinks=False):
        _scan_dir(output_dir, entry.path, files)
      elif entry.is_file(follow_symlinks=False):
        stat = entry.stat(follow_symlinks=False)
        rel_path = _normalize_rel_path(os.path.relpath(entry.path, output_dir))
        files[rel_path] = FileRecord(
          rel_path=rel_path,
          abs_path=os.path.abspath(entry.path),
          size=stat.st_size,
          mtime_ns=stat.st_mtime_ns
        )


def _has_symlink_scope_component(output_dir: str, scope_rel_path: str) -> bool:
  if scope_rel_path == '.':
    return False

  current_path = output_dir
  for path_component in scope_rel_path.split(os.sep):
    current_path = os.path.join(current_path, path_component)
    if os.path.islink(current_path):
      return True

  return False


def scan_output_scope(output_dir: str, scope_rel_path: str = '.') -> OutputInventory:
  output_dir = os.path.abspath(output_dir)
  scope_rel_path = os.path.normpath(scope_rel_path or '.')
  scope_path = output_dir if scope_rel_path == '.' else os.path.join(output_dir, scope_rel_path)
  scope_path = os.path.abspath(scope_path)
  output_dir_real = os.path.realpath(output_dir)
  scope_path_real = os.path.realpath(scope_path)

  try:
    if os.path.commonpath([output_dir, scope_path]) != output_dir:
      return OutputInventory()
    if os.path.commonpath([output_dir_real, scope_path_real]) != output_dir_real:
      return OutputInventory()
  except ValueError:
    return OutputInventory()

  if not os.path.isdir(output_dir) or _has_symlink_scope_component(output_dir, scope_rel_path) or not os.path.isdir(scope_path):
    return OutputInventory()

  files: dict[str, FileRecord] = {}
  _scan_dir(output_dir, scope_path, files)
  return OutputInventory(files=files)


def scan_output_scopes(output_dir: str, scope_rel_paths: list[str]) -> OutputInventory:
  files: dict[str, FileRecord] = {}
  for scope_rel_path in scope_rel_paths:
    files.update(scan_output_scope(output_dir, scope_rel_path).files)
  return OutputInventory(files=files)

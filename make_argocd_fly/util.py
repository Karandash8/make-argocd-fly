import logging
import logging.config
import re
import os
import copy
import ast
import json
import fnmatch
import ssl
import yaml
import urllib.request
import urllib.error
from typing import Iterable, Any
from pathlib import PurePosixPath
from collections.abc import Iterator
from importlib.metadata import version, PackageNotFoundError
from packaging.version import Version

from make_argocd_fly import default
from make_argocd_fly.cliparam import get_cli_params
from make_argocd_fly.exception import UnknownJinja2Error, InternalError, MergeError, ConfigFileError


log = logging.getLogger(__name__)


def build_path(root_dir: str, path: str, allow_missing: bool = False) -> str:
  if not path:
    log.error('Path is empty')
    raise InternalError()

  if os.path.isabs(path):
    abs_path = path
  else:
    abs_path = os.path.join(root_dir, path)

  if (not allow_missing) and (not os.path.exists(abs_path)):
    log.error(f'Path does not exist: {abs_path}')
    raise InternalError()

  return abs_path


def check_lists_equal(list_1: list, list_2: list) -> bool:
    return len(list_1) == len(list_2) and sorted(list_1) == sorted(list_2)


class VarsResolver:
  def __init__(self, var_identifier: str = default.VAR_IDENTIFIER) -> None:
    self.var_identifier = var_identifier
    self.resolution_counter = 0

  def _find_var_position(self, value: str, start: int = 0) -> tuple[int, int]:
    var_start = value.find(self.var_identifier, start)
    if var_start == -1 or value[var_start + 1] != '{':
      return (-1, -1)

    var_end = value.find('}', var_start)
    if var_end == -1:
      return (-1, -1)

    return (var_start + 1, var_end)

  def _resolve_value(self, value: str, source: dict, allow_unresolved: bool = False) -> str:
    resolved_value = ''

    start = 0
    (var_start, var_end) = self._find_var_position(value, start)

    if (var_start, var_end) == (-1, -1):
      return value

    while (var_start, var_end) != (-1, -1):
      if (var_start - 1) > start:
        resolved_value += value[start:var_start - 1]

      try:
        resolved_value += value[var_start:var_end + 1].format(**source)
        self.resolution_counter += 1
      except KeyError:
        if not allow_unresolved:
          log.error(f'Variable {value[var_start - 1:var_end + 1]} not found in vars')
          raise ConfigFileError
        else:
          resolved_value += self.var_identifier
          resolved_value += value[var_start:var_end + 1]

      start = var_end + 1
      (var_start, var_end) = self._find_var_position(value, start)

    resolved_value += value[start:]

    try:
      resolved_value = ast.literal_eval(resolved_value)
    except (SyntaxError, ValueError):
      pass

    return resolved_value

  def _iterate(self, to_resolve: dict, source: dict, value=None, initial=True, allow_unresolved: bool = False):
    value = value or to_resolve if initial else value
    if isinstance(value, dict):
      for k, v in value.items():
        value[k] = self._iterate(to_resolve, source, v, False, allow_unresolved=allow_unresolved)
    elif isinstance(value, list):
      for idx, i in enumerate(value):
        value[idx] = self._iterate(to_resolve, source, i, False, allow_unresolved=allow_unresolved)
    elif isinstance(value, str):
      value = self._resolve_value(value, source, allow_unresolved=allow_unresolved)
    return value

  def get_resolutions(self) -> int:
    return self.resolution_counter

  def resolve(self, to_resolve: dict, source: dict, allow_unresolved: bool = False) -> dict:
    self.resolution_counter = 0

    return self._iterate(copy.deepcopy(to_resolve), source, allow_unresolved=allow_unresolved)

  @staticmethod
  def resolve_all(to_resolve: dict,
                  source: dict,
                  var_identifier: str = default.VAR_IDENTIFIER,
                  allow_unresolved: bool = False) -> dict:
      resolver = VarsResolver(var_identifier)

      resolved_vars = resolver.resolve(to_resolve, source, allow_unresolved)
      while resolver.get_resolutions() > 0:
        resolved_vars = resolver.resolve(resolved_vars, source, allow_unresolved)

      return resolved_vars


def extract_single_resource(multi_resource_yml: str | None) -> Iterator[str]:
  if multi_resource_yml is None:
    log.error('Multi-resource YAML is empty')
    raise InternalError()

  for resource_yml in multi_resource_yml.split('\n---\n'):
    resource_yml = resource_yml.strip()
    resource_yml = re.sub('^---\n', '', resource_yml)
    resource_yml = re.sub('\n---$', '', resource_yml)

    if resource_yml:
      yield resource_yml


def get_app_rel_path(env_name: str, app_name: str) -> str:
  return os.path.join(env_name, app_name)


def merge_lists_without_duplicates(*lists, key_path: list | None = None):
  if not lists:
    return []

  if key_path is None:
    key_path = []

  merged = []

  for lst in lists:
    for item in lst:
      if item in merged:
        item_path = '->'.join(key_path + [f'[{merged.index(item)}]'])
        log.error(f'Duplicate item \'{item_path}\'')
        raise MergeError
      else:
        merged.append(item)

  return merged


def merge_dicts_without_duplicates(*dicts, key_path: list | None = None):
  if not dicts:
    return {}

  if key_path is None:
    key_path = []

  merged = {}

  for d in dicts:
    for key, value in d.items():
      if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
        # If the value is a dictionary and already exists in merged, merge the dictionaries
        merged[key] = merge_dicts_without_duplicates(merged[key], value, key_path=key_path + [key])
      elif isinstance(value, list) and key in merged and isinstance(merged[key], list):
        # If the value is a list and already exists in merged, merge the lists
        merged[key] = merge_lists_without_duplicates(merged[key], value, key_path=key_path + [key])
      elif key in merged:
        log.error('Duplicate key \'{}\''.format('->'.join(key_path + [key])))
        raise MergeError
      else:
        merged[key] = value

  return merged


def merge_dicts_with_overrides(*dicts):
  if not dicts:
    return {}

  merged = {}

  for d in dicts:
    for key, value in d.items():
      if value == {} and key in merged and isinstance(merged[key], dict):
        # If the value is an empty dictionary, make it an empty dictionary in merged
          merged[key] = {}
      elif isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
        merged[key] = merge_dicts_with_overrides(merged[key], value)
      elif isinstance(value, dict):
        merged[key] = merge_dicts_with_overrides({}, value)
      elif value is None and key in merged:
        # If the value is None and key exists in merged, delete the key from merged
        merged.pop(key, None)
      else:
        merged[key] = value

  return merged


def init_logging(loglevel: str) -> None:
  try:
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), default.LOG_CONFIG_FILE)) as f:
      yaml_config = yaml.safe_load(f.read())
      if loglevel in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        yaml_config['loggers']['make_argocd_fly']['level'] = loglevel
      logging.config.dictConfig(yaml_config)
  except FileNotFoundError:
    pass


def confirm_dialog() -> None:
  answer = input('Are you sure you want to continue? [y/n] (default: n) ')
  if answer.lower() not in ['y', 'yes']:
    exit()


def get_module_name() -> str:
  return __name__.split('.')[0]


def get_package_name() -> str:
  return get_module_name().replace('_', '-')


def get_current_version() -> Version | None:
  try:
    return Version(version(get_module_name()))
  except PackageNotFoundError:
    log.warning('Could not determine installed version of the package. Something is wrong or you are running from source.')
    return None


def get_latest_version() -> Version | None:
  try:
    pypi_url = f'https://pypi.org/pypi/{get_module_name()}/json'
    response = urllib.request.urlopen(pypi_url).read().decode()
    return max(Version(s) for s in json.loads(response)['releases'].keys())
  except ssl.SSLCertVerificationError:
    log.warning('SSL Certificate verification failed. Could not determine latest version of the package. '
                'Likely you have an issue with your local Python installation.')
    confirm_dialog()
    return None
  except urllib.error.URLError:
    log.warning('Could not connect to PyPI to determine latest version of the package. '
                'Make sure you have internet access and PyPI is reachable.')
    confirm_dialog()
    return None


def latest_version_check():
  if get_cli_params().skip_latest_version_check:
    log.warning('Skipping latest version check')
    return

  current_version = get_current_version()
  latest_version = get_latest_version()

  if not current_version or not latest_version:
    return

  if current_version < latest_version:
    log.warning(f'You are running {get_package_name()} ({current_version}) but there is a newer version of the '
                f'package available ({latest_version})')
    confirm_dialog()
  else:
    log.info(f'You are using the latest version of {get_package_name()} ({current_version})')


def extract_undefined_variable(message: str) -> str:
  var_match = re.search(r'\'(.+?)\' is undefined', message)
  attr_match = re.search(r'has no attribute \'(.+?)\'', message)

  variable_name = None
  if var_match:
    variable_name = var_match.group(1)
  elif attr_match:
    variable_name = attr_match.group(1)
  else:
    raise UnknownJinja2Error

  return variable_name


def ensure_list(value: Any, param_name: str) -> list[str]:
  if value is None:
    return []

  if not isinstance(value, list):
    log.error(f'Application parameter {param_name} must be a list')
    raise InternalError()

  return value


def is_match(path: str, patterns: Iterable[str]) -> bool:
  '''Match by prefix or glob; patterns are posix-like relative paths.'''
  posix = str(PurePosixPath(path))
  for pat in patterns:
    pat_posix = str(PurePosixPath(pat))

    # prefix match
    if posix.startswith(pat_posix.rstrip('/')):
      return True

    # glob match
    if fnmatch.fnmatch(posix, pat_posix):
      return True

  return False


def is_one_of(path: str, names: Iterable[str]) -> bool:
  '''True if basename (case-sensitive) is in names.'''
  return PurePosixPath(path).name in names

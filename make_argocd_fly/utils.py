import logging
import re
import os
import copy
import ast
import json
import urllib.request
from importlib.metadata import version, PackageNotFoundError
from packaging.version import Version

PACKAGE_NAME = 'make_argocd_fly'

log = logging.getLogger(__name__)


class VarsResolver:
  def __init__(self, var_identifier: str = '$') -> None:
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

  def _resolve_value(self, vars: dict, value: str) -> str:
    resolved_value = ''
    try:
      start = 0
      (var_start, var_end) = self._find_var_position(value, start)

      if (var_start, var_end) == (-1, -1):
        return value

      while (var_start, var_end) != (-1, -1):
        if (var_start - 1) > start:
          resolved_value += value[start:var_start - 1]

        resolved_value += value[var_start:var_end + 1].format(**vars)
        self.resolution_counter += 1
        start = var_end + 1

        (var_start, var_end) = self._find_var_position(value, start)

      resolved_value += value[start:]

      try:
        resolved_value = ast.literal_eval(resolved_value)
      except (SyntaxError, ValueError):
        pass

      return resolved_value
    except KeyError:
      log.error('Variable {} not found in vars'.format(value[var_start - 1:var_end + 1]))
      raise

  def _iterate(self, vars: dict, value=None, initial=True):
    value = value or vars if initial else value
    if isinstance(value, dict):
      for k, v in value.items():
        value[k] = self._iterate(vars, v, False)
    elif isinstance(value, list):
      for idx, i in enumerate(value):
        value[idx] = self._iterate(vars, i, False)
    elif isinstance(value, str):
      value = self._resolve_value(vars, value)
    return value

  def get_resolutions(self) -> int:
    return self.resolution_counter

  def resolve(self, vars: dict) -> dict:
    self.resolution_counter = 0

    return self._iterate(copy.deepcopy(vars))

  @staticmethod
  def resolve_all(vars: dict, var_identifier: str = '$') -> dict:
      resolver = VarsResolver(var_identifier)

      resolved_vars = resolver.resolve(vars)
      while resolver.get_resolutions() > 0:
        resolved_vars = resolver.resolve(resolved_vars)

      return resolved_vars


def get_filename_elements(resource_yml: str) -> list:
  filename_elements = []
  resource_kind = None
  resource_name = None

  match = re.search(r'(^kind:|\nkind:)(.+)', resource_yml)
  if match:
    resource_kind = match.group(2).strip()
    filename_elements.append(resource_kind)

  if resource_kind:
    match = re.search(r'(^metadata:|\nmetadata:).*', resource_yml)
    if match:
      match = re.search(r'(^\s\sname:|\n\s\sname:)(.+)', resource_yml[match.start():])
      if match:
        resource_name = match.group(2).strip()
        filename_elements.append(resource_name)

  return filename_elements


def extract_single_resource(multi_resource_yml: str) -> str:
  for resource_yml in multi_resource_yml.split('\n---\n'):
    resource_yml = resource_yml.strip().lstrip('---\n')

    if resource_yml:
      yield resource_yml


def generate_filename(filename_parts: list) -> str:
  if not filename_parts:
    log.error('Filename cannot be constructed')
    raise Exception

  return '_'.join([filename_part for filename_part in filename_parts if filename_part]).lower() + '.yml'


def get_app_rel_path(app_name: str, env_name: str) -> str:
  return os.path.join(env_name, app_name)


def merge_dicts(*dicts):
  if not dicts:
    return {}

  merged = {}

  for d in dicts:
    for key, value in d.items():
      if value == {} and key in merged and isinstance(merged[key], dict):
        # If the value on the right is an empty dictionary, make it an empty dictionary on the left
          merged[key] = {}
      elif isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
        merged[key] = merge_dicts(merged[key], value)
      elif isinstance(value, dict):
        merged[key] = merge_dicts({}, value)
      elif value is None:
        # If the value on the right is None, delete the key on the left
        merged.pop(key, None)
      else:
        merged[key] = value

  return merged


def latest_version_check():
  try:
    current_version = Version(version(PACKAGE_NAME))
  except PackageNotFoundError:
    raise

  pypi_url = 'https://pypi.org/pypi/{}/json'.format(PACKAGE_NAME)
  response = urllib.request.urlopen(pypi_url).read().decode()
  latest_version = max(Version(s) for s in json.loads(response)['releases'].keys())

  if current_version < latest_version:
    log.warning('You are running {} ({}) but there is a newer version of the package available ({})'.format(PACKAGE_NAME, current_version,
                                                                                                            latest_version))
    answer = input("Are you sure you want to continue? [y/n] (default: n) ")
    if answer.lower() not in ["y", "yes"]:
      exit()
  else:
    log.info('You are using the latest version of {} ({})'.format(PACKAGE_NAME, current_version))

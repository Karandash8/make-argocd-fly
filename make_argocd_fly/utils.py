import logging
import re
import os
import copy
import ast
import json
import ssl
import urllib.request
from importlib.metadata import version, PackageNotFoundError
from packaging.version import Version

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

  def _resolve_value(self, value: str, source: dict) -> str:
    resolved_value = ''
    try:
      start = 0
      (var_start, var_end) = self._find_var_position(value, start)

      if (var_start, var_end) == (-1, -1):
        return value

      while (var_start, var_end) != (-1, -1):
        if (var_start - 1) > start:
          resolved_value += value[start:var_start - 1]

        resolved_value += value[var_start:var_end + 1].format(**source)
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

  def _iterate(self, to_resolve: dict, source: dict, value=None, initial=True):
    value = value or to_resolve if initial else value
    if isinstance(value, dict):
      for k, v in value.items():
        value[k] = self._iterate(to_resolve, source, v, False)
    elif isinstance(value, list):
      for idx, i in enumerate(value):
        value[idx] = self._iterate(to_resolve, source, i, False)
    elif isinstance(value, str):
      value = self._resolve_value(value, source)
    return value

  def get_resolutions(self) -> int:
    return self.resolution_counter

  def resolve(self, to_resolve: dict, source: dict) -> dict:
    self.resolution_counter = 0

    return self._iterate(copy.deepcopy(to_resolve), source)

  @staticmethod
  def resolve_all(to_resolve: dict, source: dict, var_identifier: str = '$') -> dict:
      resolver = VarsResolver(var_identifier)

      resolved_vars = resolver.resolve(to_resolve, source)
      while resolver.get_resolutions() > 0:
        resolved_vars = resolver.resolve(resolved_vars, source)

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
    resource_yml = resource_yml.strip()
    resource_yml = re.sub('^---\n', '', resource_yml)
    resource_yml = re.sub('\n---$', '', resource_yml)

    if resource_yml:
      yield resource_yml


def generate_filename(filename_parts: list) -> str:
  if not filename_parts:
    log.error('Filename cannot be constructed')
    raise Exception

  return '_'.join([filename_part for filename_part in filename_parts if filename_part]).lower() + '.yml'


def get_app_rel_path(env_name: str, app_name: str) -> str:
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
      elif value is None and key in merged:
        # If the value on the right is None and key exists on the left, delete the key on the left
        merged.pop(key, None)
      else:
        merged[key] = value

  return merged


def confirm_dialog() -> None:
  answer = input("Are you sure you want to continue? [y/n] (default: n) ")
  if answer.lower() not in ["y", "yes"]:
    exit()


def latest_version_check():
  module_name = __name__.split('.')[0]
  package_name = module_name.replace('_', '-')

  try:
    current_version = Version(version(module_name))
  except PackageNotFoundError:
    log.warning('Could not determine installed version of the package. Something is wrong or you are running from source.')

    confirm_dialog()
    return

  try:
    pypi_url = 'https://pypi.org/pypi/{}/json'.format(module_name)
    response = urllib.request.urlopen(pypi_url).read().decode()
    latest_version = max(Version(s) for s in json.loads(response)['releases'].keys())
  except ssl.SSLCertVerificationError:
    log.warning('SSL Certificate verification failed. Could not determine latest version of the package. \
                Likely you have an issue with your local Python installation.')

    confirm_dialog()
    return

  if current_version < latest_version:
    log.warning('You are running {} ({}) but there is a newer version of the package available ({})'.format(package_name, current_version,
                                                                                                            latest_version))
    confirm_dialog()
  else:
    log.info('You are using the latest version of {} ({})'.format(package_name, current_version))

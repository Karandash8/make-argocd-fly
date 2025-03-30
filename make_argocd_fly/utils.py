import logging
import re
import os
import copy
import ast
import json
import ssl
import yaml
import urllib.request
from importlib.metadata import version, PackageNotFoundError
from packaging.version import Version

from make_argocd_fly import consts
from make_argocd_fly.params import get_params
from make_argocd_fly.exceptions import UnknownJinja2Error, InternalError


log = logging.getLogger(__name__)


def build_path(root_dir: str, path: str, allow_missing: bool = False) -> str:
  if not path:
    log.error('Path is empty')
    raise InternalError

  if os.path.isabs(path):
    abs_path = path
  else:
    abs_path = os.path.join(root_dir, path)

  if (not allow_missing) and (not os.path.exists(abs_path)):
    log.error('Path does not exist: {}'.format(abs_path))
    raise InternalError

  return abs_path


def check_lists_equal(list_1: list, list_2: list) -> bool:
    return len(list_1) == len(list_2) and sorted(list_1) == sorted(list_2)


class VarsResolver:
  def __init__(self, var_identifier: str = consts.DEFAULT_VAR_IDENTIFIER) -> None:
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
      raise KeyError

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
  def resolve_all(to_resolve: dict, source: dict, var_identifier: str = consts.DEFAULT_VAR_IDENTIFIER) -> dict:
      resolver = VarsResolver(var_identifier)

      resolved_vars = resolver.resolve(to_resolve, source)
      while resolver.get_resolutions() > 0:
        resolved_vars = resolver.resolve(resolved_vars, source)

      return resolved_vars


def extract_single_resource(multi_resource_yml: str) -> str:
  for resource_yml in multi_resource_yml.split('\n---\n'):
    resource_yml = resource_yml.strip()
    resource_yml = re.sub('^---\n', '', resource_yml)
    resource_yml = re.sub('\n---$', '', resource_yml)

    if resource_yml:
      yield resource_yml


class FilePathGenerator:
  default_file_extension = '.yml'

  def __init__(self, resource_yml: str, source_file_rel_path: str = None) -> None:
    self.resource_yml = resource_yml
    self.source_file_rel_path = source_file_rel_path

  def _extract_kind(self, resource_yml: str) -> str:
    match = re.search(r'(^kind:|\nkind:)(.+)', resource_yml)
    if match:
      return match.group(2).strip()

    return None

  def _extract_name(self, resource_yml: str) -> str:
    match = re.search(r'(^metadata:|\nmetadata:).*', resource_yml)
    if match:
      match = re.search(r'(^\s\sname:|\n\s\sname:)(.+)', resource_yml[match.start():])
      if match:
        return match.group(2).strip()

    return None

  def _extract_api_version(self, resource_yml: str) -> str:
    match = re.search(r'(^apiVersion:|\napiVersion:)(.+)', resource_yml)
    if match:
      return match.group(2).strip()

    return None

  def _extract_namespace(self, resource_yml: str) -> str:
    match = re.search(r'(^metadata:|\nmetadata:).*', resource_yml)
    if match:
      match = re.search(r'(^\s\snamespace:|\n\s\snamespace:)(.+)', resource_yml[match.start():])
      if match:
        return match.group(2).strip()

    return None

  def _extract_file_rel_path(self, source_file_rel_path: str) -> str:
    if source_file_rel_path:
      rel_path = os.path.dirname(source_file_rel_path)
      if rel_path:
        return rel_path

    return None

  def _extract_source_file_name(self, source_file_rel_path: str) -> str:
    if source_file_rel_path and os.path.basename(source_file_rel_path):
      parts = os.path.basename(source_file_rel_path).removesuffix('.j2').split('.')
      if len(parts) == 1:
        return parts[0]
      elif len(parts) > 1:
        return '.'.join(parts[:-1])

    return None

  def _extract_file_extension(self, source_file_rel_path: str) -> str:
    if source_file_rel_path:
      parts = source_file_rel_path.removesuffix('.j2').split('.')
      if len(parts) > 1:
        return '.{}'.format(parts[-1])

    return None

  def generate_from_source_file(self) -> str:
    source_file_rel_path = self._extract_file_rel_path(self.source_file_rel_path)
    source_file_name = self._extract_source_file_name(self.source_file_rel_path)
    source_file_extension = self._extract_file_extension(self.source_file_rel_path)

    if not source_file_name:
      log.debug("Filename cannot be constructed")
      raise ValueError

    if source_file_extension:
      full_filename = '{}{}'.format(source_file_name, source_file_extension)
    else:
      full_filename = source_file_name

    if source_file_rel_path:
      return os.path.join(source_file_rel_path, full_filename)

    return full_filename

  def generate_from_k8s_resource(self) -> str:
    source_file_rel_path = self._extract_file_rel_path(self.source_file_rel_path)
    resource_kind = self._extract_kind(self.resource_yml)
    resource_name = self._extract_name(self.resource_yml)
    # resource_api_version = self._extract_api_version(self.resource_yml)
    # resource_namespace = self._extract_namespace(self.resource_yml)

    if not resource_kind:
      log.debug("Filename cannot be constructed")
      raise ValueError

    elements = []
    if resource_kind:
      elements.append(resource_kind)
    if resource_name:
      elements.append(resource_name)

    full_filename = '{}{}'.format('_'.join(elements), self.default_file_extension).lower()

    if source_file_rel_path:
      return os.path.join(source_file_rel_path, full_filename)

    return full_filename


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


def init_logging(loglevel: str) -> None:
  try:
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), consts.DEFAULT_LOG_CONFIG_FILE)) as f:
      yaml_config = yaml.safe_load(f.read())
      if loglevel in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        yaml_config['loggers']['make_argocd_fly']['level'] = loglevel
      logging.config.dictConfig(yaml_config)
  except FileNotFoundError:
    pass


def confirm_dialog() -> None:
  answer = input("Are you sure you want to continue? [y/n] (default: n) ")
  if answer.lower() not in ["y", "yes"]:
    exit()


def get_module_name() -> str:
  return __name__.split('.')[0]


def get_package_name() -> str:
  return get_module_name().replace('_', '-')


def get_current_version() -> Version:
  try:
    return Version(version(get_module_name()))
  except PackageNotFoundError:
    log.warning('Could not determine installed version of the package. Something is wrong or you are running from source.')
    confirm_dialog()
    return None


def get_latest_version() -> Version:
  try:
    pypi_url = 'https://pypi.org/pypi/{}/json'.format(get_module_name())
    response = urllib.request.urlopen(pypi_url).read().decode()
    return max(Version(s) for s in json.loads(response)['releases'].keys())
  except ssl.SSLCertVerificationError:
    log.warning('SSL Certificate verification failed. Could not determine latest version of the package. \
                Likely you have an issue with your local Python installation.')
    confirm_dialog()
    return None


def latest_version_check():
  if get_params().skip_latest_version_check:
    log.warning('Skipping latest version check')
    return

  current_version = get_current_version()
  latest_version = get_latest_version()

  if not current_version or not latest_version:
    return

  if current_version < latest_version:
    log.warning('You are running {} ({}) but there is a newer version of the package available ({}).'.format(get_package_name(),
                                                                                                             current_version,
                                                                                                             latest_version))
    confirm_dialog()
  else:
    log.info('You are using the latest version of {} ({})'.format(get_package_name(), current_version))


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

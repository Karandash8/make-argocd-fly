import logging
import re
import copy

log = logging.getLogger(__name__)


class VarsResolver:
  def __init__(self, var_identifier: str = '$') -> None:
    self.var_identifier = var_identifier
    self.resolution_counter = 0

  def _resolve_var(self, vars: dict, value: str) -> str:
    if value.startswith(self.var_identifier):
      try:
        resolved_value = value[len(self.var_identifier):].format(**vars)

        if value != resolved_value:
          self.resolution_counter += 1
      except KeyError:
        resolved_value = value

      return resolved_value
    return value

  def _iterate(self, vars: dict, value=None, initial=True):
    value = value or vars if initial else value
    if isinstance(value, dict):
      for k, v in value.items():
        value[k] = self._iterate(vars, v, False)
    elif isinstance(value, list):
      for idx, i in enumerate(value):
        value[idx] = self._iterate(vars, i, False)
    elif isinstance(value, str):
      value = self._resolve_var(vars, value)
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


# TODO: rename this, logic does not align with multi_resource_parser
def resource_parser(resource_yml: str) -> tuple[str, str]:
  resource_kind = None
  resource_name = None

  match = re.search(r'(^kind:|\nkind:)(.+)', resource_yml)
  if match:
    resource_kind = match.group(2).strip()

  if resource_kind:
    match = re.search(r'(^metadata:|\nmetadata:).*', resource_yml)
    if match:
      match = re.search(r'(^\s\sname:|\n\s\sname:)(.+)', resource_yml[match.start():])
      if match:
        resource_name = match.group(2).strip()

  return (resource_kind, resource_name)


def multi_resource_parser(multi_resource_yml: str) -> tuple[str, str, str]:
  for resource_yml in multi_resource_yml.split('\n---\n'):
    resource_yml = resource_yml.strip().lstrip('---\n')
    (resource_kind, resource_name) = resource_parser(resource_yml)

    if resource_kind:
      yield (resource_kind, resource_name, resource_yml)


def generate_filename(filename_parts: list) -> str:
    if not filename_parts:
      log.error('Filename cannot be constructed')
      raise Exception

    return '_'.join([filename_part for filename_part in filename_parts if filename_part]).lower() + '.yml'


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

  return VarsResolver.resolve_all(merged)

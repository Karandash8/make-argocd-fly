import logging
import re

log = logging.getLogger(__name__)


def resource_parser(resource_yml: str) -> tuple[str, str]:
  resource_kind = None
  resource_name = None

  match = re.search('(^kind|\nkind):(.*)', resource_yml)
  if match and len(match.groups()) >= 2:
    resource_kind = match.group(2).strip()

  match = re.search('\n  name:(.*)', resource_yml)
  if match and len(match.groups()) >= 1:
    resource_name = match.group(1).strip()

  return (resource_kind, resource_name)

def multi_resource_parser(multi_resource_yml: str) -> tuple[str, str, str]:
  for resource_yml in multi_resource_yml.split('---'):
    (resource_kind, resource_name) = resource_parser(resource_yml)

    if resource_kind:
      yield (resource_kind, resource_name, resource_yml.strip())

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

import logging
import re

log = logging.getLogger(__name__)


# TODO: rename this, logic does not align with multi_resource_parser
def resource_parser(resource_yml: str) -> tuple[str, str]:
  resource_kind = None
  resource_name = None

  match_list = re.findall('(^kind:|\nkind:)(.+)', resource_yml)
  if len(match_list) > 1 or (len(match_list) == 1 and len(match_list[0]) != 2):
    log.error('Duplicate resource kind: \n%s', resource_yml)
    raise Exception

  if len(match_list) == 1:
    resource_kind = match_list[0][1].strip()

  match_list = re.findall('(^metadata:|\nmetadata:)((\n\s*#.*|\n\s+.*)*)\n\s+name:(.+)', resource_yml)
  if len(match_list) == 1 and len(match_list[0]) == 4:
    resource_name = match_list[0][3].strip()

  return (resource_kind, resource_name)

def multi_resource_parser(multi_resource_yml: str) -> tuple[str, str, str]:
  for resource_yml in multi_resource_yml.split('---\n'):
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

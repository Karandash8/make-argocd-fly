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

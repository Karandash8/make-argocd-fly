import logging
import os
import socket
from abc import ABC, abstractmethod
from jinja2 import Environment, BaseLoader, FunctionLoader, nodes, StrictUndefined
from jinja2.ext import Extension
from markupsafe import Markup

from make_argocd_fly.resource import ResourceViewer

log = logging.getLogger(__name__)


class AbstractRenderer(ABC):
  @abstractmethod
  def render(self, content: str, template_vars: dict = None) -> str:
    pass


class DummyRenderer(AbstractRenderer):
  def __init__(self) -> None:
    pass

  def render(self, content: str, template_vars: dict = None) -> str:
    return content


class DigExtension(Extension):
  def __init__(self, environment):
    super(DigExtension, self).__init__(environment)
    self.environment.filters['dig'] = self.dig_filter

  def dig_filter(self, host):
    try:
      ip_address = socket.gethostbyname(host)
      return ip_address
    except socket.gaierror:
      return None


class IncludeRawExtension(Extension):
  tags = {"include_raw"}

  def parse(self, parser):
    lineno = parser.stream.expect("name:include_raw").lineno
    template = parser.parse_expression()
    result = self.call_method("_render", [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, filename):
    return Markup(self.environment.loader.get_source(self.environment, filename)[0])


class JinjaRenderer(AbstractRenderer):
  def __init__(self, viewer: ResourceViewer = None) -> None:
    self.viewer = viewer
    if viewer:
      self.loader = FunctionLoader(self._get_template)
    else:
      self.loader = BaseLoader()
    self.env = Environment(extensions=[IncludeRawExtension,
                                       DigExtension,
                                       'jinja2_ansible_filters.AnsibleCoreFiltersExtension'],
                           loader=self.loader, undefined=StrictUndefined)

  def _get_template(self, path: str):
    files_children = self.viewer.get_files_children(os.path.basename(path))
    for file_child in files_children:
      if file_child.element_rel_path == path:
        return (file_child.content, path, None)

    log.error('Missing template {}'.format(path))
    return None

  def render(self, content: str, template_vars: dict = None, filename: str = '<template>') -> str:
    template = self.env.from_string(content)
    template.filename = filename

    return template.render(template_vars if template_vars else {})

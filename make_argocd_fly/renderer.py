import logging
import os
from abc import ABC, abstractmethod
from jinja2 import Environment, BaseLoader, FunctionLoader, nodes
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
    self.env = Environment(extensions=[IncludeRawExtension], loader=self.loader)

  def _get_template(self, path: str):
    files_children = self.viewer.get_files_children(os.path.basename(path))
    for file_child in files_children:
      if file_child.element_rel_path == path:
        return file_child.content

    log.error('Missing template {}'.format(path))
    return None

  def render(self, content: str, template_vars: dict = None) -> str:
    template = self.env.from_string(content)

    return template.render(template_vars if template_vars else {})

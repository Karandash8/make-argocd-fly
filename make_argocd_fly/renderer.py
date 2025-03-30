import logging
import os
import re
import socket
import jinja2
import typing as t
from abc import ABC, abstractmethod
from jinja2 import Environment, BaseLoader, FunctionLoader, nodes, StrictUndefined
from jinja2.ext import Extension
from jinja2.exceptions import TemplateNotFound
from markupsafe import Markup

from make_argocd_fly.resource import ResourceViewer
from make_argocd_fly.exceptions import UndefinedTemplateVariableError
from make_argocd_fly.utils import extract_undefined_variable

log = logging.getLogger(__name__)


class AbstractRenderer(ABC):
  @abstractmethod
  def render(self, content: str) -> str:
    pass


class YamlRenderer(AbstractRenderer):
  def __init__(self) -> None:
    pass

  def render(self, content: str) -> str:
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


class CustomFunctionLoader(FunctionLoader):
  def __init__(
        self,
        load_func: t.Callable[
            [str],
            t.Optional[
                t.Union[
                    str, t.Tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]]
                ]
            ],
        ],
        render_func: t.Callable[
            [str],
            t.Optional[
                t.Union[
                    str, t.Tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]]
                ]
            ],
        ],
        list_func: t.Callable[[str], t.List[str]] = None,
  ) -> None:
    super().__init__(load_func)
    self.render_func = render_func
    self.list_func = list_func

  def get_rendered(self, environment: "Environment", template: str) -> t.Tuple[str, t.Optional[str], t.Optional[t.Callable[[], bool]]]:
    rv = self.render_func(template)

    if rv is None:
      raise TemplateNotFound(template)

    if isinstance(rv, str):
      return rv, None, None

    return rv

  def list_templates(self, path: str) -> t.List[str]:
    return self.list_func(path)


class IncludeRawExtension(Extension):
  tags = {"include_raw"}

  def parse(self, parser):
    lineno = parser.stream.expect("name:include_raw").lineno
    template = parser.parse_expression()
    result = self.call_method("_render", [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, filename):
    loaded_template = self.environment.loader.get_source(self.environment, filename)
    content = loaded_template[0] if loaded_template else ''

    return Markup(content)


class IncludeAllAsYamlKVExtension(Extension):
  tags = {"include_all_as_yaml_kv"}

  def parse(self, parser):
    lineno = parser.stream.expect("name:include_all_as_yaml_kv").lineno
    template = parser.parse_expression()
    result = self.call_method("_render", [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      if child.name.endswith('.j2'):
        loaded_template = self.environment.loader.get_rendered(self.environment, child.element_rel_path)
        child_name = child.name[:-3]
      else:
        loaded_template = self.environment.loader.get_source(self.environment, child.element_rel_path)
        child_name = child.name

      child_content = loaded_template[0] if loaded_template else ''
      kv_as_yaml_str.append('{}: |\n  {}\n'.format(child_name, re.sub('\n', '\n  ', child_content.strip())))

    return Markup(''.join(kv_as_yaml_str))


class IncludeAllAsYamlListExtension(Extension):
  tags = {"include_all_as_yaml_list"}

  def parse(self, parser):
    lineno = parser.stream.expect("name:include_all_as_yaml_list").lineno
    template = parser.parse_expression()
    result = self.call_method("_render", [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      if child.name.endswith('.j2'):
        loaded_template = self.environment.loader.get_rendered(self.environment, child.element_rel_path)
      else:
        loaded_template = self.environment.loader.get_source(self.environment, child.element_rel_path)

      child_content = loaded_template[0] if loaded_template else ''
      kv_as_yaml_str.append('- {}\n'.format(re.sub('\n', '\n  ', child_content.strip())))

    return Markup(''.join(kv_as_yaml_str))


class JinjaRenderer(AbstractRenderer):
  def __init__(self, viewer: ResourceViewer = None) -> None:
    self.viewer = viewer
    if viewer:
      self.loader = CustomFunctionLoader(self._get_source, self._get_rendered, self._list_templates)
    else:
      self.loader = BaseLoader()
    self.env = Environment(extensions=[IncludeRawExtension,
                                       IncludeAllAsYamlKVExtension,
                                       IncludeAllAsYamlListExtension,
                                       DigExtension,
                                       'jinja2_ansible_filters.AnsibleCoreFiltersExtension'],
                           loader=self.loader,
                           undefined=StrictUndefined)

    self.template_vars = {}
    self.filename = '<template>'

  def _get_source(self, path: str):
    files_children = self.viewer.get_files_children(os.path.basename(path))
    for file_child in files_children:
      if file_child.element_rel_path == path:
        return (file_child.content, path, None)

    log.error('Missing template {}'.format(path))
    return None

  def _get_rendered(self, path: str):
    if not path.endswith('.j2'):
      log.error('Template {} is not a jinja template'.format(path))
      return None

    files_children = self.viewer.get_files_children(os.path.basename(path))
    for file_child in files_children:
      if file_child.element_rel_path == path:
        return (self.render(file_child.content), path, None)

    log.error('Missing template {}'.format(path))
    return None

  def _list_templates(self, path: str) -> t.List[str]:
    element = self.viewer.get_element(path)
    if not element or not element.is_dir:
      log.error('Provided path {} is not a directory'.format(path))
      return []

    return element.get_files_children('.+')

  def set_template_vars(self, template_vars: dict) -> None:
    self.template_vars = template_vars

  def set_filename(self, filename: str) -> None:
    self.filename = filename

  def render(self, content: str) -> str:
    template = self.env.from_string(content)
    template.filename = self.filename

    try:
      rendered = template.render(self.template_vars)
    except jinja2.exceptions.UndefinedError as e:
      variable_name = extract_undefined_variable(str(e))

      log.error('Variable "{}" is undefined'.format(variable_name))
      raise UndefinedTemplateVariableError(variable_name) from None

    return rendered

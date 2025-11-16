import logging
import os
import re
import socket
import jinja2
from typing import Tuple, Callable, Union, List, Any
from jinja2 import Environment, FunctionLoader, nodes, StrictUndefined
from jinja2.ext import Extension
from markupsafe import Markup

from make_argocd_fly.config import get_config
from make_argocd_fly.resource.viewer import ResourceType, ScopedViewer
from make_argocd_fly.exception import UndefinedTemplateVariableError, PathDoesNotExistError, InternalError
from make_argocd_fly.util import extract_undefined_variable

log = logging.getLogger(__name__)


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
        load_func: Callable[[str], Union[str, Tuple[str, str | None, Callable[[], bool] | None]]],
        render_func: Callable[[str], Union[str, Tuple[str, str | None, Callable[[], bool] | None]]],
        list_func: Callable[[str], List[ScopedViewer]],
  ) -> None:
    super().__init__(load_func)
    self.render_func = render_func
    self.list_func = list_func

  def get_rendered(self, environment: 'Environment', template: str) -> Tuple[str, str | None, Callable[[], bool] | None]:
    rv = self.render_func(template)

    if rv is None:
      raise PathDoesNotExistError(template)

    if isinstance(rv, str):
      return rv, None, None

    return rv

  def list_templates(self, path: str) -> List[ScopedViewer]:
    return self.list_func(path)


class RawIncludeExtension(Extension):
  tags = {'rawinclude'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:rawinclude').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, filename):
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError()

    (source, _, _) = self.environment.loader.get_source(self.environment, filename)

    return Markup(source)


class FileListExtension(Extension):
  tags = {'file_list'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:file_list').lineno
    dir_path = parser.parse_expression()
    prepend_path = parser.parse_expression() if parser.stream.skip_if('comma') else nodes.Const(None)
    result = self.call_method('_render', args=[dir_path, prepend_path], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, dir_path: str, prepend_path: str | None = None) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError()

    children = sorted(self.environment.loader.list_templates(dir_path), key=lambda child: child.name)
    yaml_names_as_list = []

    for child in children:
      # TODO: test for template here instead of checking suffix
      if child.name.endswith('.j2'):
        (source, _, _) = self.environment.loader.get_rendered(self.environment, child.rel_path)
        child_name = child.name[:-3]
      else:
        (source, _, _) = self.environment.loader.get_source(self.environment, child.rel_path)
        child_name = child.name

      # if child_content is empty, skip adding it to the yaml
      if source == '':
        log.debug('No content in ' + child_name + ', not adding to yaml')
        continue

      if prepend_path is None:
        yaml_names_as_list.append(f'- {child_name}\n')
      else:
        yaml_names_as_list.append(f'- {os.path.join(prepend_path, child_name)}\n')

    return Markup(''.join(yaml_names_as_list))


class IncludeMapExtension(Extension):
  tags = {'include_map'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:include_map').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError()

    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      if child.name.endswith('.j2'):
        (source, _, _) = self.environment.loader.get_rendered(self.environment, child.rel_path)
        child_name = child.name[:-3]
      else:
        (source, _, _) = self.environment.loader.get_source(self.environment, child.rel_path)
        child_name = child.name

      # if child_content is empty, skip adding it to the yaml
      if source == '':
        log.debug('No content in ' + child_name + ', not adding to yaml')
        continue

      kv_as_yaml_str.append('{}: |\n  {}\n'.format(child_name, re.sub('\n', '\n  ', source.strip())))

    return Markup(''.join(kv_as_yaml_str))


class RawIncludeMapExtension(Extension):
  tags = {'rawinclude_map'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:rawinclude_map').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError()

    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      (source, _, _) = self.environment.loader.get_source(self.environment, child.rel_path)
      child_name = child.name

      # if child_content is empty, skip adding it to the yaml
      if source == '':
        log.debug('No content in ' + child_name + ', not adding to yaml')
        continue

      kv_as_yaml_str.append('{}: |\n  {}\n'.format(child_name, re.sub('\n', '\n  ', source.strip())))

    return Markup(''.join(kv_as_yaml_str))


class IncludeListExtension(Extension):
  tags = {'include_list'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:include_list').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError()

    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      if child.name.endswith('.j2'):
        (source, _, _) = self.environment.loader.get_rendered(self.environment, child.rel_path)
      else:
        (source, _, _) = self.environment.loader.get_source(self.environment, child.rel_path)

      # if child_content is empty, skip adding it to the yaml
      if source == '':
        continue

      kv_as_yaml_str.append('- {}\n'.format(re.sub('\n', '\n  ', source.strip())))

    return Markup(''.join(kv_as_yaml_str))


class RawIncludeListExtension(Extension):
  tags = {'rawinclude_list'}

  def parse(self, parser):
    lineno = parser.stream.expect('name:rawinclude_list').lineno
    template = parser.parse_expression()
    result = self.call_method('_render', [template], lineno=lineno)
    return nodes.Output([result], lineno=lineno)

  def _render(self, path: str) -> str:
    if not self.environment.loader:
      log.error("Jinja2 environment loader is not set")
      raise InternalError()

    children = sorted(self.environment.loader.list_templates(path), key=lambda child: child.name)
    kv_as_yaml_str = []

    for child in children:
      (source, _, _) = self.environment.loader.get_source(self.environment, child.rel_path)

      # if child_content is empty, skip adding it to the yaml
      if source == '':
        continue

      kv_as_yaml_str.append('- {}\n'.format(re.sub('\n', '\n  ', source.strip())))

    return Markup(''.join(kv_as_yaml_str))


class JinjaRenderer():
  file_types = [resource_type for resource_type in ResourceType if
                (resource_type != ResourceType.DIRECTORY and
                 resource_type != ResourceType.DOES_NOT_EXIST)]

  def __init__(self) -> None:
    self.config = get_config()

    self.loader = CustomFunctionLoader(self._get_source, self._get_rendered, self._list_templates)
    self.env = Environment(extensions=[RawIncludeExtension,
                                       FileListExtension,
                                       IncludeMapExtension,
                                       RawIncludeMapExtension,
                                       IncludeListExtension,
                                       RawIncludeListExtension,
                                       DigExtension,
                                       'jinja2_ansible_filters.AnsibleCoreFiltersExtension'],
                           loader=self.loader,
                           undefined=StrictUndefined,
                           finalize=self._finalize)

    self.viewer = None
    self.template_vars = {}
    # Use a non-path sentinel so coverage doesn't think this is a file on disk
    self.template_origin = '<Unknown>'

    self._unresolved_re = re.compile(re.escape(self.config.cli_params.var_identifier) + r'\{[^}]+\}')

  def _finalize(self, value: Any):
    if isinstance(value, str) and not isinstance(value, Markup):
      match = self._unresolved_re.search(value)
      if match:
        unresolved = match.group(0)
        log.error(f'Unresolved variable reference: {unresolved}')
        raise UndefinedTemplateVariableError(unresolved)

    return value

  def _get_source(self, path: str):
    if not self.viewer:
      log.error("Resource viewer is not set")
      raise InternalError()

    try:
      target = self.viewer.go_to(os.path.normpath(path))
    except PathDoesNotExistError:
      log.error(f'Path does not exist {path}')
      raise

    return (target.content, path, None)

  def _get_rendered(self, path: str):
    if not self.viewer:
      log.error("Resource viewer is not set")
      raise InternalError()

    try:
      target = self.viewer.go_to(os.path.normpath(path))
    except PathDoesNotExistError:
      log.error(f'Path does not exist {path}')
      raise

    return (self.render(target.content), path, None)

  def _list_templates(self, path: str) -> List[ScopedViewer]:
    if not self.viewer:
      log.error("Resource viewer is not set")
      raise InternalError()

    return list(self.viewer.search_subresources(resource_types=self.file_types,
                                                search_subdirs=[os.path.normpath(path)]))

  def set_template_vars(self, template_vars: dict) -> None:
    self.template_vars = template_vars

  def set_template_origin(self, origin: str) -> None:
    self.template_origin = origin

  def set_resource_viewer(self, viewer: ScopedViewer) -> None:
    self.viewer = viewer

  def render(self, content: str) -> str:
    template = self.env.from_string(content)
    template.filename = self.template_origin

    try:
      rendered = template.render(self.template_vars)
    except jinja2.exceptions.UndefinedError as e:
      variable_name = extract_undefined_variable(str(e))

      log.error(f'Variable "{variable_name}" is undefined')
      raise UndefinedTemplateVariableError(variable_name) from None
    except TypeError:
      log.error(f'Likely a missing variable in template {self.template_origin}')
      raise UndefinedTemplateVariableError('Unknown variable in template') from None

    return rendered

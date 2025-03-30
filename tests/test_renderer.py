import pytest
import jinja2
import textwrap
from make_argocd_fly.resource import ResourceViewer
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.exceptions import UndefinedTemplateVariableError

###############
### _get_source
###############

def test_JinjaRenderer_get_source_simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  TEMPLATE = 'Template content'
  template = dir_root / 'template.txt.j2'
  template.write_text(TEMPLATE)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  assert renderer._get_source('template.txt.j2') == (TEMPLATE, 'template.txt.j2', None)

def test_JinjaRenderer_get_source_does_not_exist(tmp_path, caplog):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  assert renderer._get_source('template.txt.j2') == None
  assert 'Missing template template.txt.j2' in caplog.text

def test_JinjaRenderer_get_source_same_filename(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template content 0'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)
  dir_1 = dir_root / 'dir_1'
  dir_1.mkdir()
  TEMPLATE_1 = 'Template content 1'
  template_1 = dir_1 / 'template.txt.j2'
  template_1.write_text(TEMPLATE_1)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  assert renderer._get_source('dir_1/template.txt.j2') == (TEMPLATE_1, 'dir_1/template.txt.j2', None)

#################
### _get_rendered
#################

def test_JinjaRenderer_get_rendered_simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  TEMPLATE = 'Template {{ var }}'
  template = dir_root / 'template.txt.j2'
  template.write_text(TEMPLATE)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)
  renderer.set_template_vars({'var': 'content'})

  assert renderer._get_rendered('template.txt.j2') == ('Template content', 'template.txt.j2', None)

def test_JinjaRenderer_get_rendered_does_not_exist(tmp_path, caplog):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  assert renderer._get_rendered('template.txt.j2') == None
  assert 'Missing template template.txt.j2' in caplog.text

def test_JinjaRenderer_get_rendered_not_a_jinja_template(tmp_path, caplog):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  assert renderer._get_rendered('template.txt') == None
  assert 'Template template.txt is not a jinja template' in caplog.text

###########
### Loaders
###########

def test_JinjaRenderer_base_loader_render_simple():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content line 2
  '''

  assert renderer.render(TEMPLATE) == TEMPLATE

def test_JinjaRenderer_base_loader_render_with_var():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content {{ line_2 }}
  '''

  renderer.set_template_vars({'line_2': 'line 2'})
  assert renderer.render(TEMPLATE) == \
  '''\
  Template content line 1
  Template content line 2
  '''

def test_JinjaRenderer_base_loader_render_with_undefined_var():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content {{ undefined_var }}
  '''

  with pytest.raises(UndefinedTemplateVariableError):
    assert renderer.render(TEMPLATE)

def test_JinjaRenderer_base_loader_render_with_include():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  {% include 'template.txt.j2' %}
  '''

  with pytest.raises(jinja2.exceptions.TemplateNotFound):
    renderer.render(TEMPLATE)

def test_JinjaRenderer_function_loader_render_with_include_raw(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template content 0'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)

  resource_viewer = ResourceViewer(str(dir_0))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
  Template content line 1
  {% include_raw 'template.txt.j2' %}
  '''

  assert renderer.render(TEMPLATE) == \
  '''\
  Template content line 1
  Template content 0
  '''

def test_JinjaRenderer_function_loader_render_with_include(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template {{ content }}'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)

  resource_viewer = ResourceViewer(str(dir_0))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
  Template content line 1
  {% include 'template.txt.j2' %}
  '''

  renderer.set_template_vars({'content': 'content 0'})
  assert renderer.render(TEMPLATE) == \
  '''\
  Template content line 1
  Template content 0
  '''

def test_JinjaRenderer_function_loader_render_with_include_inception(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = "{% include 'template_inception.txt.j2' %}"
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)
  TEMPLATE_1 = 'Template {{ content }}'
  template_1 = dir_0 / 'template_inception.txt.j2'
  template_1.write_text(TEMPLATE_1)

  resource_viewer = ResourceViewer(str(dir_0))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
  Template content line 1
  {% include 'template.txt.j2' %}
  '''

  renderer.set_template_vars({'content': 'content 0'})
  assert renderer.render(TEMPLATE) == \
  '''\
  Template content line 1
  Template content 0
  '''

def test_JinjaRenderer_function_loader_render_with_dig_filter():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content {{ 'localhost' | dig }}
  '''

  assert renderer.render(TEMPLATE) == \
  '''\
  Template content line 1
  Template content 127.0.0.1
  '''

def test_JinjaRenderer_function_loader_render_with_include_all_as_yaml_kv(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  files = dir_0 / 'files'
  files.mkdir()
  files_subdir = files / 'files_subdir'
  files_subdir.mkdir()
  FILE_1 = 'key_1: {{ content }}'
  file_1 = files / 'file_1.yml.j2'
  file_1.write_text(FILE_1)
  FILE_2 = 'key_2: value 2'
  file_2 = files / 'file_2.yml'
  file_2.write_text(FILE_2)
  FILE_3 = '''\
  key_3: value 3
  multiline_key_3: |
    multiline value 3
  '''
  file_3 = files_subdir / 'file_3.yml'
  file_3.write_text(textwrap.dedent(FILE_3))

  resource_viewer = ResourceViewer(str(dir_0))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
    {% include_all_as_yaml_kv 'files' %}
  '''

  renderer.set_template_vars({'content': 'value 1'})
  output = '''\
    file_1.yml: |
      key_1: value 1
    file_2.yml: |
      key_2: value 2
    file_3.yml: |
      key_3: value 3
      multiline_key_3: |
        multiline value 3
  '''

  assert textwrap.dedent(output) == renderer.render(textwrap.dedent(TEMPLATE))

def test_JinjaRenderer_function_loader_render_with_include_all_as_yaml_list(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  files = dir_0 / 'files'
  files.mkdir()
  files_subdir = files / 'files_subdir'
  files_subdir.mkdir()
  FILE_1 = 'key_1: {{ content }}'
  file_1 = files / 'file_1.yml.j2'
  file_1.write_text(FILE_1)
  FILE_2 = 'key_2: value 2'
  file_2 = files / 'file_2.yml'
  file_2.write_text(FILE_2)
  FILE_3 = '''\
  key_3: value 3
  multiline_key_3: |
    multiline value 3
  '''
  file_3 = files_subdir / 'file_3.yml'
  file_3.write_text(textwrap.dedent(FILE_3))

  resource_viewer = ResourceViewer(str(dir_0))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
    {% include_all_as_yaml_list 'files' %}
  '''

  renderer.set_template_vars({'content': 'value 1'})
  output = '''\
    - key_1: value 1
    - key_2: value 2
    - key_3: value 3
      multiline_key_3: |
        multiline value 3
  '''

  assert textwrap.dedent(output) == renderer.render(textwrap.dedent(TEMPLATE))

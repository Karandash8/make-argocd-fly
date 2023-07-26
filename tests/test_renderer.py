import pytest
import jinja2
from make_argocd_fly.resource import ResourceViewer
from make_argocd_fly.renderer import JinjaRenderer

def test_JinjaRenderer_get_template_simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  TEMPLATE = 'Template content'
  template = dir_root / 'template.txt.j2'
  template.write_text(TEMPLATE)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  assert renderer._get_template('template.txt.j2') == TEMPLATE

def test_JinjaRenderer_get_template_does_not_exist(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  assert renderer._get_template('template.txt.j2') == None

def test_JinjaRenderer_get_template_same_filename(tmp_path):
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

  assert renderer._get_template('dir_1/template.txt.j2') == TEMPLATE_1

def test_JinjaRenderer_base_loader_render_simple():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content line 2
  '''

  assert renderer.render(TEMPLATE) == TEMPLATE

def test_JinjaRenderer_base_loader_render_with_vars():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content {{ line_2 }}
  '''

  assert renderer.render(TEMPLATE, {'line_2': 'line 2'}) == \
  '''\
  Template content line 1
  Template content line 2
  '''

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

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
  Template content line 1
  {% include_raw 'dir_0/template.txt.j2' %}
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

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
  Template content line 1
  {% include 'dir_0/template.txt.j2' %}
  '''

  assert renderer.render(TEMPLATE, {'content': 'content 0'}) == \
  '''\
  Template content line 1
  Template content 0
  '''

def test_JinjaRenderer_function_loader_render_with_inception(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = "{% include 'dir_0/template_inception.txt.j2' %}"
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)
  TEMPLATE_1 = 'Template {{ content }}'
  template_1 = dir_0 / 'template_inception.txt.j2'
  template_1.write_text(TEMPLATE_1)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()
  renderer = JinjaRenderer(resource_viewer)

  TEMPLATE = '''\
  Template content line 1
  {% include 'dir_0/template.txt.j2' %}
  '''

  assert renderer.render(TEMPLATE, {'content': 'content 0'}) == \
  '''\
  Template content line 1
  Template content 0
  '''

import pytest
import jinja2
import textwrap
from make_argocd_fly.resource.viewer import build_scoped_viewer
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.exception import UndefinedTemplateVariableError, InternalError, PathDoesNotExistError

###############
### _get_source
###############

def test_JinjaRenderer__get_source__no_viewer_set():
  renderer = JinjaRenderer()

  with pytest.raises(InternalError):
    renderer._get_source('template.txt.j2')

def test_JinjaRenderer_get_source_simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  TEMPLATE = 'Template content'
  template = dir_root / 'template.txt.j2'
  template.write_text(TEMPLATE)

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  assert renderer._get_source('template.txt.j2') == (TEMPLATE, 'template.txt.j2', None)

def test_JinjaRenderer_get_source_does_not_exist(tmp_path, caplog):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  with pytest.raises(PathDoesNotExistError):
    renderer._get_source('template.txt.j2')
  assert 'Path does not exist template.txt.j2' in caplog.text

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

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  assert renderer._get_source('dir_1/template.txt.j2') == (TEMPLATE_1, 'dir_1/template.txt.j2', None)

def test_JinjaRenderer__get_source__similar_filenames(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template content 0'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)
  TEMPLATE_1 = 'Template content 1'
  template_1 = dir_0 / 'extra-template.txt.j2'
  template_1.write_text(TEMPLATE_1)

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  assert renderer._get_source('dir_0/template.txt.j2') == (TEMPLATE_0, 'dir_0/template.txt.j2', None)

def test_JinjaRenderer__get_source__similar_filenames_2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template content 0'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)
  TEMPLATE_1 = 'Template content 1'
  template_1 = dir_0 / 'template.txt.j2-extra'
  template_1.write_text(TEMPLATE_1)

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  assert renderer._get_source('dir_0/template.txt.j2') == (TEMPLATE_0, 'dir_0/template.txt.j2', None)

#################
### _get_rendered
#################

def test_JinjaRenderer__get_rendered__no_viewer_set():
  renderer = JinjaRenderer()

  with pytest.raises(InternalError):
    renderer._get_rendered('template.txt.j2')

def test_JinjaRenderer_get_rendered_simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  TEMPLATE = 'Template {{ var }}'
  template = dir_root / 'template.txt.j2'
  template.write_text(TEMPLATE)

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  renderer.set_template_vars({'var': 'content'})

  assert renderer._get_rendered('template.txt.j2') == ('Template content', 'template.txt.j2', None)

def test_JinjaRenderer_get_rendered_does_not_exist(tmp_path, caplog):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  with pytest.raises(PathDoesNotExistError):
    renderer._get_rendered('template.txt.j2')
  assert 'Path does not exist template.txt.j2' in caplog.text

def test_JinjaRenderer__get_rendered__similar_filenames(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template content 0'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)
  TEMPLATE_1 = 'Template content 1'
  template_1 = dir_0 / 'extra-template.txt.j2'
  template_1.write_text(TEMPLATE_1)

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  assert renderer._get_rendered('dir_0/template.txt.j2') == (TEMPLATE_0, 'dir_0/template.txt.j2', None)

def test_JinjaRenderer__get_rendered__similar_filenames_2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template content 0'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)
  TEMPLATE_1 = 'Template content 1'
  template_1 = dir_0 / 'template.txt.j2-extra'
  template_1.write_text(TEMPLATE_1)

  viewer = build_scoped_viewer(str(dir_root))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  assert renderer._get_rendered('dir_0/template.txt.j2') == (TEMPLATE_0, 'dir_0/template.txt.j2', None)

###########
### JinjaRenderer.render
###########

def test_JinjaRenderer__render_simple():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content line 2
  '''

  assert renderer.render(TEMPLATE) == TEMPLATE

def test_JinjaRenderer__render_with_var():
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

def test_JinjaRenderer__no_viewer_set():
  renderer = JinjaRenderer()

  with pytest.raises(InternalError):
    renderer._get_rendered('template.txt.j2')

def test_JinjaRenderer__render_with_undefined_var():
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content line 1
  Template content {{ undefined_var }}
  '''

  with pytest.raises(UndefinedTemplateVariableError):
    assert renderer.render(TEMPLATE)

def test_JinjaRenderer__render_with_unresolved_var(caplog):
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content {{ var }}
  '''

  renderer.set_template_vars({'var': '${unresolved_var}'})
  with pytest.raises(UndefinedTemplateVariableError):
    assert renderer.render(TEMPLATE)
  assert 'Unresolved variable reference: ${unresolved_var}' in caplog.text

def test_JinjaRenderer__render_with_unresolved_var_in_string(caplog):
  renderer = JinjaRenderer()

  TEMPLATE = '''\
  Template content {{ var }}
  '''

  renderer.set_template_vars({'var': 'str_${unresolved_var}_str'})
  with pytest.raises(UndefinedTemplateVariableError):
    assert renderer.render(TEMPLATE)
  assert 'Unresolved variable reference: ${unresolved_var}' in caplog.text

def test_JinjaRenderer__render_missing_template(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  renderer = JinjaRenderer()
  renderer.set_resource_viewer(build_scoped_viewer(str(dir_root)))

  TEMPLATE = '''\
  Template content line 1
  {% include 'template.txt.j2' %}
  '''

  with pytest.raises(PathDoesNotExistError):
    renderer.render(TEMPLATE)

def test_JinjaRenderer__render_with_rawinclude(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template {{ var }} content 0'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
  Template content line 1
  {% rawinclude 'template.txt.j2' %}
  '''

  assert renderer.render(TEMPLATE) == \
  '''\
  Template content line 1
  Template {{ var }} content 0
  '''

def test_JinjaRenderer__render_with_include(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  TEMPLATE_0 = 'Template {{ content }}'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

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

def test_JinjaRenderer__render_with_include_from_parent_dir(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_0 = dir_root / 'dir_0'
  dir_0.mkdir()
  dir_1 = dir_root / 'dir_1'
  dir_1.mkdir()
  TEMPLATE_0 = 'Template {{ content }}'
  template_0 = dir_0 / 'template.txt.j2'
  template_0.write_text(TEMPLATE_0)

  viewer = build_scoped_viewer(str(dir_root))
  viewer = viewer.go_to('dir_1')
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
  Template content line 1
  {% include '../dir_0/template.txt.j2' %}
  '''

  renderer.set_template_vars({'content': 'content 0'})
  assert renderer.render(TEMPLATE) == \
  '''\
  Template content line 1
  Template content 0
  '''

def test_JinjaRenderer__render_with_include_inception(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

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

def test_JinjaRenderer__render_with_dig_filter():
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

def test_JinjaRenderer__render_with_file_list_without_prefix(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
    {% file_list 'files' %}
  '''

  renderer.set_template_vars({'content': 'value 1'})
  output = '''\
    - file_1.yml
    - file_2.yml
  '''

  assert textwrap.dedent(output) == renderer.render(textwrap.dedent(TEMPLATE))

def test_JinjaRenderer__render_with_file_list_with_prefix(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
    {% file_list 'files', '/etc/' %}
  '''

  renderer.set_template_vars({'content': 'value 1'})
  output = '''\
    - /etc/file_1.yml
    - /etc/file_2.yml
  '''

  assert textwrap.dedent(output) == renderer.render(textwrap.dedent(TEMPLATE))

def test_JinjaRenderer__render_with_include_map(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
    {% include_map 'files' %}
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

def test_JinjaRenderer__render_with_rawinclude_map(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
    {% rawinclude_map 'files' %}
  '''

  renderer.set_template_vars({'content': 'value 1'})
  output = '''\
    file_1.yml.j2: |
      key_1: {{ content }}
    file_2.yml: |
      key_2: value 2
    file_3.yml: |
      key_3: value 3
      multiline_key_3: |
        multiline value 3
  '''

  assert textwrap.dedent(output) == renderer.render(textwrap.dedent(TEMPLATE))

def test_JinjaRenderer__render_with_include_list(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
    {% include_list 'files' %}
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


def test_JinjaRenderer__render_with_rawinclude_list(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_0))
  renderer = JinjaRenderer()
  renderer.set_resource_viewer(viewer)

  TEMPLATE = '''\
    {% rawinclude_list 'files' %}
  '''

  renderer.set_template_vars({'content': 'value 1'})
  output = '''\
    - key_1: {{ content }}
    - key_2: value 2
    - key_3: value 3
      multiline_key_3: |
        multiline value 3
  '''

  assert textwrap.dedent(output) == renderer.render(textwrap.dedent(TEMPLATE))

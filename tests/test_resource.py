import os
import pytest
from make_argocd_fly.resource.viewer import ResourceViewer, ResourceType, get_resource_type
from make_argocd_fly.resource.writer import ResourceWriter
from make_argocd_fly.exception import ResourceViewerIsFake, InternalError
from make_argocd_fly.util import check_lists_equal

##################
### get_resource_type
##################

def test_get_resource_type__does_not_exist(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'non_existent_file.txt'

  resource_type = get_resource_type(os.path.join(dir_root, file_path))
  assert resource_type == ResourceType.DOES_NOT_EXIST

def test_get_resource_type__yaml(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yaml'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type = get_resource_type(os.path.join(dir_root, file_path))
  assert resource_type == ResourceType.YAML

def test_get_resource_type__yaml_2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yml'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type = get_resource_type(os.path.join(dir_root, file_path))
  assert resource_type == ResourceType.YAML

def test_get_resource_type__jinja2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type = get_resource_type(os.path.join(dir_root, file_path))
  assert resource_type == ResourceType.JINJA2

def test_get_resource_type__unknown(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.txt'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type = get_resource_type(os.path.join(dir_root, file_path))
  assert resource_type == ResourceType.UNKNOWN

def test_get_resource_type__directory(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_subdir = dir_root / 'subdir'
  dir_subdir.mkdir()

  resource_type = get_resource_type(str(dir_subdir))
  assert resource_type == ResourceType.DIRECTORY

##################
### ResourceViewer
##################

def test_ResourceViewer__with_empty_dir(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(str(dir_root))

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == '.'
  assert resource_viewer.resource_type == ResourceType.DIRECTORY
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.content == ''
  assert check_lists_equal(resource_viewer.children, [])

def test_ResourceViewer__with_file(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'element.txt'
  FILE_0_CONTENT = 'test'
  file_root_0 = dir_root / file_path
  file_root_0.write_text(FILE_0_CONTENT)

  resource_viewer = ResourceViewer(str(dir_root), file_path)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == file_path
  assert resource_viewer.resource_type == get_resource_type(os.path.join(str(dir_root), file_path))
  assert resource_viewer.name == file_path
  assert resource_viewer.content == FILE_0_CONTENT
  assert check_lists_equal(resource_viewer.children, [])

def test_ResourceViewer__with_non_normalized_path(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  normalized_file_path = './element.txt'
  file_path = 'element.txt'
  FILE_0_CONTENT = 'test'
  file_root_0 = dir_root / file_path
  file_root_0.write_text(FILE_0_CONTENT)

  resource_viewer = ResourceViewer(str(dir_root), normalized_file_path)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == file_path
  assert resource_viewer.resource_type == get_resource_type(os.path.join(str(dir_root), file_path))
  assert resource_viewer.name == file_path
  assert resource_viewer.content == FILE_0_CONTENT
  assert check_lists_equal(resource_viewer.children, [])

def test_ResourceViewer__with_directories_and_files(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_root_0 = dir_root / 'dir_root_0'
  dir_root_0.mkdir()
  dir_root_1 = dir_root / 'dir_root_1'
  dir_root_1.mkdir()
  dir_root_1_0 = dir_root_1 / 'dir_root_1_0'
  dir_root_1_0.mkdir()
  FILE_0_CONTENT = 'Content of file 0'
  file_root_0 = dir_root / 'file_root_0.txt'
  file_root_0.write_text(FILE_0_CONTENT)
  FILE_1_CONTENT = 'Content of file 1'
  file_root_1_0_0 = dir_root_1_0 / 'file_root_1_0_0.txt'
  file_root_1_0_0.write_text(FILE_1_CONTENT)
  FILE_2_CONTENT = ''
  file_root_1_0_1 = dir_root_1_0 / 'file_root_1_0_1.txt'
  file_root_1_0_1.write_text(FILE_2_CONTENT)

  resource_viewer = ResourceViewer(str(dir_root))

  assert resource_viewer.children is not None

  for child in resource_viewer.children:
    if child.name == 'dir_root_0':
      dir_root_0_idx = resource_viewer.children.index(child)
    elif child.name == 'dir_root_1':
      dir_root_1_idx = resource_viewer.children.index(child)
    elif child.name == 'file_root_0.txt':
      file_root_0_idx = resource_viewer.children.index(child)

  for child in resource_viewer.children[dir_root_1_idx].children[0].children:
    if child.name == 'file_root_1_0_0.txt':
      file_root_1_0_0_idx = resource_viewer.children[dir_root_1_idx].children[0].children.index(child)
    elif child.name == 'file_root_1_0_1.txt':
      file_root_1_0_1_idx = resource_viewer.children[dir_root_1_idx].children[0].children.index(child)

  # root dir
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.element_rel_path == '.'
  assert resource_viewer.resource_type == ResourceType.DIRECTORY
  assert resource_viewer.content == ''
  assert len(resource_viewer.children) == 3

  # dir with a dir
  assert resource_viewer.children[dir_root_1_idx].name == "dir_root_1"
  assert resource_viewer.children[dir_root_1_idx].element_rel_path == 'dir_root_1'
  assert resource_viewer.children[dir_root_1_idx].resource_type == ResourceType.DIRECTORY
  assert resource_viewer.children[dir_root_1_idx].content == ''
  assert len(resource_viewer.children[dir_root_1_idx].children) == 1

  # dir with files
  assert resource_viewer.children[dir_root_1_idx].children[0].name == "dir_root_1_0"
  assert resource_viewer.children[dir_root_1_idx].children[0].element_rel_path == 'dir_root_1/dir_root_1_0'
  assert resource_viewer.children[dir_root_1_idx].children[0].resource_type == ResourceType.DIRECTORY
  assert resource_viewer.children[dir_root_1_idx].children[0].content == ''
  assert len(resource_viewer.children[dir_root_1_idx].children[0].children) == 2

  # empty file
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].name == "file_root_1_0_1.txt"
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_1.txt'
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].resource_type == get_resource_type(os.path.join(str(dir_root), 'dir_root_1/dir_root_1_0/file_root_1_0_1.txt'))
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].content == FILE_2_CONTENT
  assert len(resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_1_idx].children) == 0

  # file with content
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].name == "file_root_1_0_0.txt"
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_0.txt'
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].resource_type == get_resource_type(os.path.join(str(dir_root), 'dir_root_1/dir_root_1_0/file_root_1_0_0.txt'))
  assert resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].content == FILE_1_CONTENT
  assert len(resource_viewer.children[dir_root_1_idx].children[0].children[file_root_1_0_0_idx].children) == 0

  # file in root dir
  assert resource_viewer.children[file_root_0_idx].name == "file_root_0.txt"
  assert resource_viewer.children[file_root_0_idx].element_rel_path == 'file_root_0.txt'
  assert resource_viewer.children[file_root_0_idx].resource_type == get_resource_type(os.path.join(str(dir_root), 'file_root_0.txt'))
  assert resource_viewer.children[file_root_0_idx].content == FILE_0_CONTENT
  assert len(resource_viewer.children[file_root_0_idx].children) == 0

  # empty dir
  assert resource_viewer.children[dir_root_0_idx].name == "dir_root_0"
  assert resource_viewer.children[dir_root_0_idx].element_rel_path == 'dir_root_0'
  assert resource_viewer.children[dir_root_0_idx].resource_type == ResourceType.DIRECTORY
  assert resource_viewer.children[dir_root_0_idx].content == ''
  assert len(resource_viewer.children[dir_root_0_idx].children) == 0

##################
### ResourceViewer.search_subresources()
##################

def test_ResourceViewer__search_subresources__by_type(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_yaml = dir_root / 'file.yaml'
  file_yaml.write_text('key: file')
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  file_app_txt = dir_app / 'app.txt'
  file_app_txt.write_text('text file content')
  file_app_yaml = dir_app / 'app.yaml'
  file_app_yaml.write_text('key: app')
  file_app_yaml_2 = dir_app / 'app_2.yml'
  file_app_yaml_2.write_text('key: app_2')
  file_app_j2 = dir_app / 'app.j2'
  file_app_j2.write_text('key: {{ value }}')
  dir_app_empty = dir_app / 'empty'
  dir_app_empty.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  all_resources = list(resource_viewer.search_subresources())
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in all_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML),
                            ('app', '', ResourceType.DIRECTORY),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN),
                            ('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML),
                            ('app.j2', 'key: {{ value }}', ResourceType.JINJA2),
                            ('empty', '', ResourceType.DIRECTORY)])

  none_resources = list(resource_viewer.search_subresources(resource_types=[]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in none_resources], [])

  unknown_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.UNKNOWN]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in unknown_resources],
                           [('app.txt', 'text file content', ResourceType.UNKNOWN)])

  yaml_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in yaml_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML),
                            ('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML)])

  jinja2_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.JINJA2]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in jinja2_resources],
                           [('app.j2', 'key: {{ value }}', ResourceType.JINJA2)])

  non_existent_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.DOES_NOT_EXIST]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in non_existent_resources], [])

  directory_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.DIRECTORY]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in directory_resources],
                           [('app', '', ResourceType.DIRECTORY),
                            ('empty', '', ResourceType.DIRECTORY)])

  yaml_and_jinja2_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML, ResourceType.JINJA2]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in yaml_and_jinja2_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML),
                            ('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML),
                            ('app.j2', 'key: {{ value }}', ResourceType.JINJA2)])

  directory_and_yaml_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.DIRECTORY, ResourceType.YAML]))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in directory_and_yaml_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML),
                            ('app', '', ResourceType.DIRECTORY),
                            ('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML),
                            ('empty', '', ResourceType.DIRECTORY)])

def test_ResourceViewer__search_subresources__by_pattern(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_yaml = dir_root / 'file.yaml'
  file_yaml.write_text('key: file')
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  file_app_txt = dir_app / 'app.txt'
  file_app_txt.write_text('text file content')
  file_app_yaml = dir_app / 'app.yaml'
  file_app_yaml.write_text('key: app')
  file_app_yaml_2 = dir_app / 'app_2.yml'
  file_app_yaml_2.write_text('key: app_2')
  file_app_j2 = dir_app / 'app.j2'
  file_app_j2.write_text('key: {{ value }}')
  dir_app_empty = dir_app / 'empty'
  dir_app_empty.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='app'))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in pattern_resources],
                           [('app', '', ResourceType.DIRECTORY),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN),
                            ('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML),
                            ('app.j2', 'key: {{ value }}', ResourceType.JINJA2)])

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='app.j2'))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in pattern_resources],
                           [('app.j2', 'key: {{ value }}', ResourceType.JINJA2)])

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='file'))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in pattern_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML)])

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='non_existent'))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in pattern_resources], [])

  pattern_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], name_pattern='app'))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in pattern_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML)])

def test_ResourceViewer__search_subresources__by_subdirs(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_yaml = dir_root / 'file.yaml'
  file_yaml.write_text('key: file')
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  file_app_txt = dir_app / 'app.txt'
  file_app_txt.write_text('text file content')
  file_app_yaml = dir_app / 'app.yaml'
  file_app_yaml.write_text('key: app')
  file_app_yaml_2 = dir_app / 'app_2.yml'
  file_app_yaml_2.write_text('key: app_2')
  file_app_j2 = dir_app / 'app.j2'
  file_app_j2.write_text('key: {{ value }}')
  dir_app_empty = dir_app / 'empty'
  dir_app_empty.mkdir()
  dir_app_subdir = dir_app / 'subdir'
  dir_app_subdir.mkdir()
  file_app_subdir_yaml = dir_app_subdir / 'app_subdir.yaml'
  file_app_subdir_yaml.write_text('key: app_subdir')

  resource_viewer = ResourceViewer(str(dir_root))

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app']))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in subdir_resources],
                           [('app.txt', 'text file content', ResourceType.UNKNOWN),
                            ('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML),
                            ('app.j2', 'key: {{ value }}', ResourceType.JINJA2),
                            ('empty', '', ResourceType.DIRECTORY),
                            ('subdir', '', ResourceType.DIRECTORY),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app/empty']))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in subdir_resources], [])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app/subdir']))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in subdir_resources],
                           [('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['subdir']))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in subdir_resources], [])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], depth=1))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in subdir_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], depth=2))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in subdir_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], name_pattern='app_'))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in subdir_resources],
                           [('app_2.yml', 'key: app_2', ResourceType.YAML),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML)])

def test_ResourceViewer__search_subresources__by_depth(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_yaml = dir_root / 'file.yaml'
  file_yaml.write_text('key: file')
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  file_app_yaml = dir_app / 'app.yaml'
  file_app_yaml.write_text('key: app')
  file_app_yaml_2 = dir_app / 'app_2.yml'
  file_app_yaml_2.write_text('key: app_2')

  resource_viewer = ResourceViewer(str(dir_root))

  depth_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], depth=2))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in depth_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML),
                            ('app.yaml', 'key: app', ResourceType.YAML),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML)])

  depth_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], depth=1))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in depth_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML)])

  depth_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], depth=0))
  assert check_lists_equal([(res.name, res.content, res.resource_type) for res in depth_resources], [])

##################
### ResourceViewer._get_child()
##################

def test_ResourceViewer__get_child__fake(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(os.path.join(dir_root, 'non_existent_element'))

  with pytest.raises(ResourceViewerIsFake):
    resource_viewer._get_child('file.txt')

def test_ResourceViewer__get_child__simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  child = resource_viewer._get_child('app')
  assert child is not None
  assert child.name == 'app'

##################
### ResourceViewer.get_element()
##################

def test_ResourceViewer__get_element__fake(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(os.path.join(dir_root, 'non_existent_element'))

  with pytest.raises(ResourceViewerIsFake):
    resource_viewer.get_element('file.txt')

def test_ResourceViewer__get_element__simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  child = resource_viewer.get_element('app')
  assert child is not None
  assert child.name == 'app'

def test_ResourceViewer__get_element__non_existent_simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  child = resource_viewer.get_element('app')
  assert child == None

def test_ResourceViewer__get_element__path(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_subdir = dir_root / 'subdir'
  dir_subdir.mkdir()
  dir_app = dir_subdir / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  child = resource_viewer.get_element('subdir/app')
  assert child is not None
  assert child.name == 'app'
  assert child.element_rel_path == 'subdir/app'

def test_ResourceViewer__get_element__non_existent_path(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_subdir = dir_root / 'subdir'
  dir_subdir.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  child = resource_viewer.get_element('subdir/app')
  assert child == None

##################
### ResourceViewer.get_children()
##################

def test_ResourceViewer__get_children__fake(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(os.path.join(dir_root, 'non_existent_element'))

  with pytest.raises(ResourceViewerIsFake):
    resource_viewer.get_children()

def test_ResourceViewer__get_children__simple(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()

  resource_viewer = ResourceViewer(str(dir_root))

  children = resource_viewer.get_children()
  assert len(children) == 1
  assert children[0].name == 'app'

##################
### ResourceWriter
##################

def test_ResourceWriter__with_default_values(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  assert resource_writer.output_dir_abs_path == str(dir_output)
  assert resource_writer.resources == {}

##################
### ResourceWriter.store_resource()
##################

def test_ResourceWriter__store_resource__multiple(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))
  env_name = 'env'

  resource_writer.store_resource('/a/b/c', 'resource body 1')
  resource_writer.store_resource('/a/b/d', 'resource body 2')
  resource_writer.store_resource('/a/b/e', 'resource body 3')

  assert len(resource_writer.resources) == 3
  assert '/a/b/c' in resource_writer.resources
  assert resource_writer.resources['/a/b/c'] == 'resource body 1'
  assert '/a/b/d' in resource_writer.resources
  assert resource_writer.resources['/a/b/d'] == 'resource body 2'
  assert '/a/b/e' in resource_writer.resources
  assert resource_writer.resources['/a/b/e'] == 'resource body 3'

def test_ResourceWriter__store_resource__duplicate(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))
  env_name = 'env'

  resource_writer.store_resource('/a/b/c', 'resource body 1')
  with pytest.raises(InternalError):
      resource_writer.store_resource('/a/b/c', 'resource body 1')
  assert 'Resource (/a/b/c) already exists' in caplog.text

def test_ResourceWriter__store_resource__undefined_dir_rel_path(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))
  env_name = 'env'

  with pytest.raises(InternalError):
    resource_writer.store_resource('', 'resource body 1')
  assert 'Parameter `file_path` is undefined' in caplog.text

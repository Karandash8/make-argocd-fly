import os
import pytest
from make_argocd_fly.resource.viewer import ResourceViewer, _get_resource_params, ResourceType, build_scoped_viewer
from make_argocd_fly.resource.writer import GenericWriter, YamlWriter
from make_argocd_fly.exception import InternalError, YamlObjectRequiredError
from make_argocd_fly.param import ApplicationTypes
from make_argocd_fly.util import check_lists_equal

##################
### _get_resource_params
##################

def test_get_resource_type__does_not_exist(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'non_existent_file.txt'

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.DOES_NOT_EXIST, False)

def test_get_resource_type__directory(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_subdir = dir_root / 'subdir'
  dir_subdir.mkdir()

  resource_type, template = _get_resource_params(str(dir_subdir))
  assert (resource_type, template) == (ResourceType.DIRECTORY, False)

def test_get_resource_type__yaml(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yaml'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, False)

def test_get_resource_type__yaml_2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yml'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, False)

def test_get_resource_type__unknown(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.txt'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.UNKNOWN, False)

def test_get_resource_type__template(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.UNKNOWN, True)

def test_get_resource_type__template_yml(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yml.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, True)

def test_get_resource_type__template_yml_2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yaml.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, True)

def test_get_resource_type__template_unknown(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.txt.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = _get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.UNKNOWN, True)

##################
### ScopedViewer
##################

def test_ScopedViewer__with_empty_dir(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()

  viewer = build_scoped_viewer(str(dir_root))

  assert viewer.path == str(dir_root)
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.DIRECTORY
  assert viewer.template == False
  assert viewer.name == 'dir_root'
  assert viewer.content == ''
  assert len(list(viewer.iter_children())) == 0

def test_ScopedViewer__with_file(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'element.txt'
  FILE_0_CONTENT = 'test'
  file_root_0 = dir_root / file_path
  file_root_0.write_text(FILE_0_CONTENT)

  viewer = build_scoped_viewer(str(dir_root))

  assert viewer.path == str(dir_root)
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.DIRECTORY
  assert viewer.template == False
  assert viewer.name == 'dir_root'
  assert viewer.content == ''
  assert len(list(viewer.iter_children())) == 1

def test_ScopedViewer__with_go_to_to_file(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'element.txt'
  FILE_0_CONTENT = 'test'
  file_root_0 = dir_root / file_path
  file_root_0.write_text(FILE_0_CONTENT)

  viewer = build_scoped_viewer(str(dir_root))
  viewer = viewer.go_to(file_path)

  assert viewer.path == str(file_root_0)
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.UNKNOWN
  assert viewer.template == False
  assert viewer.name == file_path
  assert viewer.content == FILE_0_CONTENT
  assert len(list(viewer.iter_children())) == 0

def test_ScopedViewer__with_directories_and_files(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_root))

  # root dir
  assert viewer.name == 'dir_root'
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.DIRECTORY
  assert viewer.template == False
  assert viewer.content == ''
  assert len(list(viewer.iter_children())) == 3

  # dir with a dir
  assert viewer.child('dir_root_1').name == 'dir_root_1'
  assert viewer.child('dir_root_1').rel_path == 'dir_root_1'
  assert viewer.child('dir_root_1').resource_type == ResourceType.DIRECTORY
  assert viewer.child('dir_root_1').template == False
  assert viewer.child('dir_root_1').content == ''
  assert len(list(viewer.child('dir_root_1').iter_children())) == 1

  # dir with files
  assert viewer.child('dir_root_1').child('dir_root_1_0').name == 'dir_root_1_0'
  assert viewer.child('dir_root_1').child('dir_root_1_0').rel_path == 'dir_root_1/dir_root_1_0'
  assert viewer.child('dir_root_1').child('dir_root_1_0').resource_type == ResourceType.DIRECTORY
  assert viewer.child('dir_root_1').child('dir_root_1_0').template == False
  assert viewer.child('dir_root_1').child('dir_root_1_0').content == ''
  assert len(list(viewer.child('dir_root_1').child('dir_root_1_0').iter_children())) == 2

  # empty file
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_1.txt').name == 'file_root_1_0_1.txt'
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_1.txt').rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_1.txt'
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_1.txt').resource_type == ResourceType.UNKNOWN
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_1.txt').template == False
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_1.txt').content == FILE_2_CONTENT
  assert len(list(viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_1.txt').iter_children())) == 0

  # file with content
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_0.txt').name == 'file_root_1_0_0.txt'
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_0.txt').rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_0.txt'
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_0.txt').resource_type == ResourceType.UNKNOWN
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_0.txt').template == False
  assert viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_0.txt').content == FILE_1_CONTENT
  assert len(list(viewer.child('dir_root_1').child('dir_root_1_0').child('file_root_1_0_0.txt').iter_children())) == 0

  # file in root dir
  assert viewer.child('file_root_0.txt').name == 'file_root_0.txt'
  assert viewer.child('file_root_0.txt').rel_path == 'file_root_0.txt'
  assert viewer.child('file_root_0.txt').resource_type == ResourceType.UNKNOWN
  assert viewer.child('file_root_0.txt').template == False
  assert viewer.child('file_root_0.txt').content == FILE_0_CONTENT
  assert len(list(viewer.child('file_root_0.txt').iter_children())) == 0

  # empty dir
  assert viewer.child('dir_root_0').name == 'dir_root_0'
  assert viewer.child('dir_root_0').rel_path == 'dir_root_0'
  assert viewer.child('dir_root_0').resource_type == ResourceType.DIRECTORY
  assert viewer.child('dir_root_0').template == False
  assert viewer.child('dir_root_0').content == ''
  assert len(list(viewer.child('dir_root_0').iter_children())) == 0

def test_ScopedViewer__with_go_to_to_directories_and_files(tmp_path):
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

  viewer = build_scoped_viewer(str(dir_root))

  # root dir
  assert viewer.name == 'dir_root'
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.DIRECTORY
  assert viewer.template == False
  assert viewer.content == ''
  assert len(list(viewer.iter_children())) == 3

  viewer = viewer.go_to('dir_root_1')

  # dir_root_1
  assert viewer.name == 'dir_root_1'
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.DIRECTORY
  assert viewer.template == False
  assert viewer.content == ''
  assert len(list(viewer.iter_children())) == 1

  viewer = viewer.go_to('dir_root_1_0')

  # dir_root_1_0
  assert viewer.name == 'dir_root_1_0'
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.DIRECTORY
  assert viewer.template == False
  assert viewer.content == ''
  assert len(list(viewer.iter_children())) == 2

  viewer = viewer.go_to('file_root_1_0_0.txt')

  # file_root_1_0_0.txt
  assert viewer.name == 'file_root_1_0_0.txt'
  assert viewer.rel_path == '.'
  assert viewer.resource_type == ResourceType.UNKNOWN
  assert viewer.template == False
  assert viewer.content == FILE_1_CONTENT
  assert len(list(viewer.iter_children())) == 0

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
  file_app_yml_j2 = dir_app / 'app.yml.j2'
  file_app_yml_j2.write_text('key_2: {{ value }}')
  dir_app_empty = dir_app / 'empty'
  dir_app_empty.mkdir()

  viewer = build_scoped_viewer(str(dir_root))

  all_resources = list(viewer.search_subresources())
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in all_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app', '', ResourceType.DIRECTORY, False),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('empty', '', ResourceType.DIRECTORY, False)])

  none_resources = list(viewer.search_subresources(resource_types=[]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in none_resources], [])

  unknown_resources = list(viewer.search_subresources(resource_types=[ResourceType.UNKNOWN]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in unknown_resources],
                           [('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True)])

  yaml_resources = list(viewer.search_subresources(resource_types=[ResourceType.YAML]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in yaml_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  non_existent_resources = list(viewer.search_subresources(resource_types=[ResourceType.DOES_NOT_EXIST]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in non_existent_resources], [])

  directory_resources = list(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in directory_resources],
                           [('app', '', ResourceType.DIRECTORY, False),
                            ('empty', '', ResourceType.DIRECTORY, False)])

  directory_and_yaml_resources = list(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY, ResourceType.YAML]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in directory_and_yaml_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app', '', ResourceType.DIRECTORY, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('empty', '', ResourceType.DIRECTORY, False)])

def test_ResourceViewer__search_subresources__if_template(tmp_path):
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
  file_app_yml_j2 = dir_app / 'app.yml.j2'
  file_app_yml_j2.write_text('key_2: {{ value }}')
  dir_app_empty = dir_app / 'empty'
  dir_app_empty.mkdir()

  viewer = build_scoped_viewer(str(dir_root))

  template_resources = list(viewer.search_subresources(template=True))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in template_resources],
                           [('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  non_template_resources = list(viewer.search_subresources(template=False))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in non_template_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app', '', ResourceType.DIRECTORY, False),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('empty', '', ResourceType.DIRECTORY, False)])

  all_resources = list(viewer.search_subresources())
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in all_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app', '', ResourceType.DIRECTORY, False),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('empty', '', ResourceType.DIRECTORY, False)])

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
  file_app_yml_j2 = dir_app / 'app.yml.j2'
  file_app_yml_j2.write_text('key_2: {{ value }}')
  dir_app_empty = dir_app / 'empty'
  dir_app_empty.mkdir()

  viewer = build_scoped_viewer(str(dir_root))

  pattern_resources = list(viewer.search_subresources(name_pattern='app'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources],
                           [('app', '', ResourceType.DIRECTORY, False),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  pattern_resources = list(viewer.search_subresources(name_pattern='app.j2'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources],
                           [('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True)])

  pattern_resources = list(viewer.search_subresources(name_pattern='file'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False)])

  pattern_resources = list(viewer.search_subresources(name_pattern='non_existent'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources], [])

  pattern_resources = list(viewer.search_subresources(resource_types=[ResourceType.YAML], name_pattern='app'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

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
  file_app_yml_j2 = dir_app / 'app.yml.j2'
  file_app_yml_j2.write_text('key_2: {{ value }}')
  dir_app_empty = dir_app / 'empty'
  dir_app_empty.mkdir()
  dir_app_subdir = dir_app / 'subdir'
  dir_app_subdir.mkdir()
  file_app_subdir_yaml = dir_app_subdir / 'app_subdir.yaml'
  file_app_subdir_yaml.write_text('key: app_subdir')

  viewer = build_scoped_viewer(str(dir_root))

  subdir_resources = list(viewer.search_subresources(search_subdirs=['app']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('empty', '', ResourceType.DIRECTORY, False),
                            ('subdir', '', ResourceType.DIRECTORY, False),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(viewer.search_subresources(search_subdirs=['app/empty']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources], [])

  subdir_resources = list(viewer.search_subresources(search_subdirs=['app/subdir']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(viewer.search_subresources(search_subdirs=['subdir']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources], [])

  subdir_resources = list(viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], depth=1))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  subdir_resources = list(viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], depth=2))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], name_pattern='app_'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(viewer.search_subresources(search_subdirs=['.'], resource_types=[ResourceType.YAML], depth=1))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False)])

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
  file_app_yml_j2 = dir_app / 'app.yml.j2'
  file_app_yml_j2.write_text('key_2: {{ value }}')

  viewer = build_scoped_viewer(str(dir_root))

  depth_resources = list(viewer.search_subresources(resource_types=[ResourceType.YAML], depth=2))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in depth_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  depth_resources = list(viewer.search_subresources(resource_types=[ResourceType.YAML], depth=1))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in depth_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False)])

  depth_resources = list(viewer.search_subresources(resource_types=[ResourceType.YAML], depth=0))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in depth_resources], [])


def _paths(children):
  # Helper to extract rel paths in a deterministic order
  return sorted([c.rel_path for c in children])

def _write(p, text=''):
  p.parent.mkdir(parents=True, exist_ok=True)
  p.write_text(text)

def test_ResourceViewer__search_subresources__no_excludes_yaml_non_template(tmp_path):
  root = tmp_path / 'src'
  # files
  _write(root / 'a' / 'config.yml', 'k: v')
  _write(root / 'a' / 'config.yml.j2', 'k: {{ v }}')  # template, should be excluded when template=False
  _write(root / 'a' / 'notes.txt', 'n/a')             # non-yaml
  _write(root / 'b' / 'sub' / 'keep.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                        template=False,
                                        search_subdirs=None,
                                        excludes=None)

  assert _paths(children) == [
    'a/config.yml',
    'b/sub/keep.yml',
    'b/sub/secret.yml',
  ]

def test_ResourceViewer__search_subresources__exclude_by_prefix(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'config.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'keep.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                        template=False,
                                        excludes=['b/sub'])

  assert _paths(children) == ['a/config.yml']

def test_ResourceViewer__search_subresources__exclude_by_glob(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'b' / 'sub' / 'keep.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret-values.yaml', 'k: v')
  _write(root / 'b' / 'other' / 'secret.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                        template=False,
                                        excludes=['b/**/secret*'])

  assert _paths(children) == ['b/sub/keep.yml']

def test_ResourceViewer__search_subresources__template_true_picks_j2_yaml(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'plain.yml', 'k: v')
  _write(root / 'a' / 'tpl.yml.j2', 'k: {{ v }}')
  _write(root / 'a' / 'tpl.txt.j2', 'plain')  # non-yaml template -> not YAML ResourceType

  viewer = build_scoped_viewer(str(root))

  # Non-templates
  non_tpl = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                       template=False)
  assert _paths(non_tpl) == ['a/plain.yml']

  # Templates
  tpl = viewer.search_subresources(
    resource_types=[ResourceType.YAML],
    template=True,
  )
  # Only YAML templates (e.g., *.yml.j2 / *.yaml.j2) should be included
  assert _paths(tpl) == ['a/tpl.yml.j2']

def test_ResourceViewer__search_subresources__search_subdirs_limits_scope(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'one.yml', 'k: v')
  _write(root / 'b' / 'two.yml', 'k: v')
  _write(root / 'b' / 'nested' / 'three.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                        template=False,
                                        search_subdirs=['a'])
  assert _paths(children) == ['a/one.yml']

def test_ResourceViewer__search_subresources__combined_template_and_excludes(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'env' / 'values.yml.j2', 'k: {{ v }}')
  _write(root / 'env' / 'patch.yml.j2', 'k: {{ v }}')
  _write(root / 'env' / 'readme.txt', 'ignore')

  viewer = build_scoped_viewer(str(root))

  tpl = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                   template=True,
                                   excludes=['env/patch*'])
  assert _paths(tpl) == ['env/values.yml.j2']

def test_ResourceViewer__search_subresources__include_by_prefix(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'config.yml', 'k: v')
  _write(root / 'a' / 'other.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'keep.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                        template=False,
                                        includes=['a'])

  assert _paths(children) == [
    'a/config.yml',
    'a/other.yml',
  ]

def test_ResourceViewer__search_subresources__include_by_glob(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'config.yml', 'k: v')
  _write(root / 'a' / 'config-prod.yml', 'k: v')
  _write(root / 'a' / 'notes.txt', 'n/a')
  _write(root / 'b' / 'config-prod.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                        template=False,
                                        includes=['**/*prod*'])

  assert _paths(children) == [
    'a/config-prod.yml',
    'b/config-prod.yml',
  ]

def test_ResourceViewer__search_subresources__include_and_exclude_combined(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'env' / 'values.yml', 'k: v')
  _write(root / 'env' / 'secret.yml', 'k: v')
  _write(root / 'env' / 'secret-values.yml', 'k: v')
  _write(root / 'other' / 'values.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                        template=False,
                                        includes=['env/**'],
                                        excludes=['**/secret*'])

  assert _paths(children) == ['env/values.yml']

def test_ResourceViewer__search_subresources__include_limits_to_yaml_templates(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'env' / 'tpl.yml.j2', 'k: {{ v }}')
  _write(root / 'env' / 'tpl.txt.j2', 'plain')
  _write(root / 'env' / 'plain.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  # template=True + YAML types + include should still behave predictably
  tpl = viewer.search_subresources(resource_types=[ResourceType.YAML],
                                   template=True,
                                   includes=['env/**'])
  assert _paths(tpl) == ['env/tpl.yml.j2']

##################
### GenericWriter
##################

def test_GenericWriter__write__simple(tmp_path):
  dir_root = tmp_path / 'output'
  dir_root.mkdir()
  file = dir_root / 'file.txt'
  content = 'content'

  writer = GenericWriter()
  writer.write(output_path=file,
               data=content,
               env_name='env',
               app_name='app',
               origin='/a/b/c')

  assert file.exists()
  assert file.read_text() == content

def test_GenericWriter__write__multiline(tmp_path):
  dir_root = tmp_path / 'output'
  dir_root.mkdir()
  file = dir_root / 'file.txt'
  content = 'line 1\nline 2\nline 3'

  writer = GenericWriter()
  writer.write(output_path=file,
               data=content,
               env_name='env',
               app_name='app',
               origin='/a/b/c')

  assert file.exists()
  assert file.read_text() == content

##################
### YamlWriter
##################

def test_YamlWriter__write__dict_simple(tmp_path):
  dir_root = tmp_path / 'output'
  dir_root.mkdir()
  file = dir_root / 'file.yaml'
  data = {'key': 'value'}

  writer = YamlWriter()
  writer.write(output_path=file,
               data=data,
               env_name='env',
               app_name='app',
               origin='/a/b/c')

  assert file.exists()
  # Adjust this if your dumper formatting changes
  content = file.read_text()
  # we expect a simple YAML mapping with one key
  assert 'key: value' in content

def test_YamlWriter__write__dict_multiline(tmp_path):
  dir_root = tmp_path / 'output'
  dir_root.mkdir()
  file = dir_root / 'file.yaml'
  data = {
    'key': 'value',
    'another_key': 'another_value',
  }

  writer = YamlWriter()
  writer.write(output_path=file,
               data=data,
               env_name='env',
               app_name='app',
               origin='/a/b/c')

  assert file.exists()
  content = file.read_text()
  # Order isn’t strictly guaranteed unless you fix sort_keys,
  # so just assert both lines are there.
  assert 'key: value' in content
  assert 'another_key: another_value' in content

def test_YamlWriter__write__non_mapping_raises(tmp_path):
  dir_root = tmp_path / 'output'
  dir_root.mkdir()
  file = dir_root / 'file.yaml'

  writer = YamlWriter()

  with pytest.raises(YamlObjectRequiredError):
    writer.write(output_path=file,
                 data='key: value',      # not a dict
                 env_name='env',
                 app_name='app',
                 origin='/a/b/c')

  with pytest.raises(YamlObjectRequiredError):
    writer.write(output_path=file,
                 data=['a', 'b'],        # also not a dict
                 env_name='env',
                 app_name='app',
                 origin='/a/b/c')

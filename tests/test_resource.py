import os
import pytest
from make_argocd_fly.resource.viewer import ResourceViewer, get_resource_params
from make_argocd_fly.resource.type import ResourceType
from make_argocd_fly.context.data import OutputResource
from make_argocd_fly.resource.persistence import ResourcePersistence, writer_factory, GenericWriter, YamlWriter
from make_argocd_fly.exception import InternalError
from make_argocd_fly.util import check_lists_equal

##################
### get_resource_params
##################

def test_get_resource_type__does_not_exist(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'non_existent_file.txt'

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.DOES_NOT_EXIST, False)

def test_get_resource_type__directory(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_subdir = dir_root / 'subdir'
  dir_subdir.mkdir()

  resource_type, template = get_resource_params(str(dir_subdir))
  assert (resource_type, template) == (ResourceType.DIRECTORY, False)

def test_get_resource_type__yaml(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yaml'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, False)

def test_get_resource_type__yaml_2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yml'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, False)

def test_get_resource_type__unknown(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.txt'
  file_root = dir_root / file_path
  file_root.write_text('key: value')

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.UNKNOWN, False)

def test_get_resource_type__template(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.UNKNOWN, True)

def test_get_resource_type__template_yml(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yml.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, True)

def test_get_resource_type__template_yml_2(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.yaml.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.YAML, True)

def test_get_resource_type__template_unknown(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  file_path = 'file.txt.j2'
  file_root = dir_root / file_path
  file_root.write_text('key: {{ value }}')

  resource_type, template = get_resource_params(os.path.join(dir_root, file_path))
  assert (resource_type, template) == (ResourceType.UNKNOWN, True)

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
  assert resource_viewer.template == False
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.content == ''
  assert resource_viewer.subresources == {}

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
  assert resource_viewer.resource_type == ResourceType.UNKNOWN
  assert resource_viewer.template == False
  assert resource_viewer.name == file_path
  assert resource_viewer.content == FILE_0_CONTENT
  assert resource_viewer.subresources == {}

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
  assert resource_viewer.resource_type == ResourceType.UNKNOWN
  assert resource_viewer.template == False
  assert resource_viewer.name == file_path
  assert resource_viewer.content == FILE_0_CONTENT
  assert resource_viewer.subresources == {}

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

  assert resource_viewer.subresources

  # root dir
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.element_rel_path == '.'
  assert resource_viewer.resource_type == ResourceType.DIRECTORY
  assert resource_viewer.template == False
  assert resource_viewer.content == ''
  assert len(resource_viewer.subresources) == 3

  # dir with a dir
  assert resource_viewer.subresources['dir_root_1'].name == 'dir_root_1'
  assert resource_viewer.subresources['dir_root_1'].element_rel_path == 'dir_root_1'
  assert resource_viewer.subresources['dir_root_1'].resource_type == ResourceType.DIRECTORY
  assert resource_viewer.subresources['dir_root_1'].template == False
  assert resource_viewer.subresources['dir_root_1'].content == ''
  assert len(resource_viewer.subresources['dir_root_1'].subresources) == 1

  # dir with files
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].name == 'dir_root_1_0'
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].element_rel_path == 'dir_root_1/dir_root_1_0'
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].resource_type == ResourceType.DIRECTORY
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].template == False
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].content == ''
  assert len(resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources) == 2

  # empty file
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_1.txt'].name == 'file_root_1_0_1.txt'
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_1.txt'].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_1.txt'
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_1.txt'].resource_type == ResourceType.UNKNOWN
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_1.txt'].template == False
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_1.txt'].content == FILE_2_CONTENT
  assert len(resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_1.txt'].subresources) == 0

  # file with content
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_0.txt'].name == 'file_root_1_0_0.txt'
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_0.txt'].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_0.txt'
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_0.txt'].resource_type == ResourceType.UNKNOWN
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_0.txt'].template == False
  assert resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_0.txt'].content == FILE_1_CONTENT
  assert len(resource_viewer.subresources['dir_root_1'].subresources['dir_root_1/dir_root_1_0'].subresources['dir_root_1/dir_root_1_0/file_root_1_0_0.txt'].subresources) == 0

  # file in root dir
  assert resource_viewer.subresources['file_root_0.txt'].name == 'file_root_0.txt'
  assert resource_viewer.subresources['file_root_0.txt'].element_rel_path == 'file_root_0.txt'
  assert resource_viewer.subresources['file_root_0.txt'].resource_type == ResourceType.UNKNOWN
  assert resource_viewer.subresources['file_root_0.txt'].template == False
  assert resource_viewer.subresources['file_root_0.txt'].content == FILE_0_CONTENT
  assert len(resource_viewer.subresources['file_root_0.txt'].subresources) == 0

  # empty dir
  assert resource_viewer.subresources['dir_root_0'].name == 'dir_root_0'
  assert resource_viewer.subresources['dir_root_0'].element_rel_path == 'dir_root_0'
  assert resource_viewer.subresources['dir_root_0'].resource_type == ResourceType.DIRECTORY
  assert resource_viewer.subresources['dir_root_0'].template == False
  assert resource_viewer.subresources['dir_root_0'].content == ''
  assert len(resource_viewer.subresources['dir_root_0'].subresources) == 0

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

  resource_viewer = ResourceViewer(str(dir_root))

  all_resources = list(resource_viewer.search_subresources())
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in all_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app', '', ResourceType.DIRECTORY, False),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('empty', '', ResourceType.DIRECTORY, False)])

  none_resources = list(resource_viewer.search_subresources(resource_types=[]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in none_resources], [])

  unknown_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.UNKNOWN]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in unknown_resources],
                           [('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True)])

  yaml_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in yaml_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  non_existent_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.DOES_NOT_EXIST]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in non_existent_resources], [])

  directory_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.DIRECTORY]))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in directory_resources],
                           [('app', '', ResourceType.DIRECTORY, False),
                            ('empty', '', ResourceType.DIRECTORY, False)])

  directory_and_yaml_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.DIRECTORY, ResourceType.YAML]))
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

  resource_viewer = ResourceViewer(str(dir_root))

  template_resources = list(resource_viewer.search_subresources(template=True))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in template_resources],
                           [('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  non_template_resources = list(resource_viewer.search_subresources(template=False))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in non_template_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app', '', ResourceType.DIRECTORY, False),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('empty', '', ResourceType.DIRECTORY, False)])

  all_resources = list(resource_viewer.search_subresources())
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

  resource_viewer = ResourceViewer(str(dir_root))

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='app'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources],
                           [('app', '', ResourceType.DIRECTORY, False),
                            ('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='app.j2'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources],
                           [('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True)])

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='file'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False)])

  pattern_resources = list(resource_viewer.search_subresources(name_pattern='non_existent'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in pattern_resources], [])

  pattern_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], name_pattern='app'))
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

  resource_viewer = ResourceViewer(str(dir_root))

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app.txt', 'text file content', ResourceType.UNKNOWN, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.j2', 'key: {{ value }}', ResourceType.UNKNOWN, True),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('empty', '', ResourceType.DIRECTORY, False),
                            ('subdir', '', ResourceType.DIRECTORY, False),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app/empty']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources], [])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app/subdir']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['subdir']))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources], [])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], depth=1))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], depth=2))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['app'], resource_types=[ResourceType.YAML], name_pattern='app_'))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in subdir_resources],
                           [('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app_subdir.yaml', 'key: app_subdir', ResourceType.YAML, False)])

  subdir_resources = list(resource_viewer.search_subresources(search_subdirs=['.'], resource_types=[ResourceType.YAML], depth=1))
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

  resource_viewer = ResourceViewer(str(dir_root))

  depth_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], depth=2))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in depth_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False),
                            ('app.yaml', 'key: app', ResourceType.YAML, False),
                            ('app_2.yml', 'key: app_2', ResourceType.YAML, False),
                            ('app.yml.j2', 'key_2: {{ value }}', ResourceType.YAML, True)])

  depth_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], depth=1))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in depth_resources],
                           [('file.yaml', 'key: file', ResourceType.YAML, False)])

  depth_resources = list(resource_viewer.search_subresources(resource_types=[ResourceType.YAML], depth=0))
  assert check_lists_equal([(res.name, res.content, res.resource_type, res.template) for res in depth_resources], [])

##################
### ResourcePersistence
##################

def test_ResourceWriter__with_default_values(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourcePersistence(str(dir_output), 'env', 'app')

  assert resource_writer.output_dir_abs_path == str(dir_output)
  assert resource_writer.resources == {}

##################
### ResourcePersistence.store_resource()
##################

def test_ResourceWriter__store_resource__multiple(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  env_name = 'env'
  app_name = 'app'
  resource_writer = ResourcePersistence(str(dir_output), env_name, app_name)

  resource_1 = OutputResource(
      resource_type=ResourceType.YAML,
      data='resource body 1',
      source='/a/b/c',
      output_path='/a/b/c'
  )
  resource_2 = OutputResource(
      resource_type=ResourceType.YAML,
      data='resource body 2',
      source='/a/b/d',
      output_path='/a/b/d'
  )
  resource_3 = OutputResource(
      resource_type=ResourceType.YAML,
      data='resource body 3',
      source='/a/b/e',
      output_path='/a/b/e'
  )
  resource_writer.store_resource(resource_1)
  resource_writer.store_resource(resource_2)
  resource_writer.store_resource(resource_3)

  assert resource_writer.resources == {'/a/b/c': resource_1,
                                        '/a/b/d': resource_2,
                                        '/a/b/e': resource_3}

def test_ResourceWriter__store_resource__duplicate(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  env_name = 'env'
  app_name = 'app'
  resource_writer = ResourcePersistence(str(dir_output), env_name, app_name)

  resource_writer.store_resource(OutputResource(
      resource_type=ResourceType.YAML,
      data='resource body 1',
      source='/a/b/c',
      output_path='/a/b/c'
  ))
  with pytest.raises(InternalError):
      resource_writer.store_resource(OutputResource(
          resource_type=ResourceType.YAML,
          data='resource body 1',
          source='/a/b/c',
          output_path='/a/b/c'
      ))
  assert 'Resource (/a/b/c) already exists' in caplog.text

def test_ResourceWriter__store_resource__undefined_dir_rel_path(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  env_name = 'env'
  app_name = 'app'
  resource_writer = ResourcePersistence(str(dir_output), env_name, app_name)

  with pytest.raises(InternalError):
    resource_writer.store_resource(OutputResource(
        resource_type=ResourceType.YAML,
        data='resource body 1',
        source='/a/b/c',
        output_path=''
    ))
  assert 'Parameter `output_path` is not set for resource' in caplog.text


##################
### writer_factory
##################

def test_writer_factory__yaml():
  assert isinstance(writer_factory(ResourceType.YAML), YamlWriter)

def test_writer_factory__generic():
  assert isinstance(writer_factory(ResourceType.UNKNOWN), GenericWriter)

def test_writer_factory__unsupported(caplog):
  with pytest.raises(InternalError):
    writer_factory(ResourceType.DIRECTORY)
  assert 'Cannot write resource of type DIRECTORY' in caplog.text

  with pytest.raises(InternalError):
    writer_factory(ResourceType.DOES_NOT_EXIST)
  assert 'Cannot write resource of type DOES_NOT_EXIST' in caplog.text

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
               source='/a/b/c')

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
               source='/a/b/c')

  assert file.exists()
  assert file.read_text() == content

##################
### YamlWriter
##################

def test_YamlWriter__write__simple(tmp_path):
  dir_root = tmp_path / 'output'
  dir_root.mkdir()
  file = dir_root / 'file.yaml'
  content = 'key: value'

  expected_content = f'---\n{content}\n'

  writer = YamlWriter()
  writer.write(output_path=file,
               data=content,
               env_name='env',
               app_name='app',
               source='/a/b/c')

  assert file.exists()
  assert file.read_text() == expected_content

def test_YamlWriter__write__multiline(tmp_path):
  dir_root = tmp_path / 'output'
  dir_root.mkdir()
  file = dir_root / 'file.yaml'
  content = 'key: value\nanother_key: another_value'

  expected_content = '---\nkey: value\nanother_key: another_value\n'

  writer = YamlWriter()
  writer.write(output_path=file,
               data=content,
               env_name='env',
               app_name='app',
               source='/a/b/c')

  assert file.exists()
  assert file.read_text() == expected_content

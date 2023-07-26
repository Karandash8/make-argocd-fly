import pytest
from make_argocd_fly.resource import ResourceViewer, ResourceWriter


def test_ResourceViewer_constructor_with_default_values(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  resource_viewer = ResourceViewer(str(dir_root))

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == '.'
  assert resource_viewer.is_dir is True
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.content is None
  assert resource_viewer.children == []

def test_ResourceViewer_constructor_with_file(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  element_path = 'custom/element.txt'
  is_dir = False
  resource_viewer = ResourceViewer(str(dir_root), element_path, is_dir)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == element_path
  assert resource_viewer.is_dir == is_dir
  assert resource_viewer.name == 'element.txt'
  assert resource_viewer.content is None
  assert resource_viewer.children == []

def test_ResourceViewer_constructor_with_dir(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  element_path = 'custom/element'
  is_dir = True
  resource_viewer = ResourceViewer(str(dir_root), element_path, is_dir)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == element_path
  assert resource_viewer.is_dir == is_dir
  assert resource_viewer.name == 'element'
  assert resource_viewer.content is None
  assert resource_viewer.children == []

def test_ResourceViewer_constructor_with_non_normalized_path(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  element_path = './other_element'
  resource_viewer = ResourceViewer(str(dir_root), element_path)

  assert resource_viewer.root_element_abs_path == str(dir_root)
  assert resource_viewer.element_rel_path == 'other_element'
  assert resource_viewer.is_dir is True
  assert resource_viewer.name == 'other_element'
  assert resource_viewer.content is None
  assert resource_viewer.children == []

def test_ResourceViewer_constructor_with_non_existing_path(caplog):
  with pytest.raises(Exception):
      ResourceViewer('/non/existing/path')
  assert 'Path does not exist' in caplog.text

def test_ResourceViewer_build_with_non_existing_path(tmp_path, caplog):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  element_path = 'other_element'
  resource_viewer = ResourceViewer(str(dir_root), element_path)

  with pytest.raises(Exception):
      resource_viewer.build()
  assert 'Path does not exist' in caplog.text

def test_ResourceViewer_build_with_directories_and_files(tmp_path):
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
  resource_viewer.build()

  # root dir
  assert resource_viewer.name == 'dir_root'
  assert resource_viewer.element_rel_path == '.'
  assert resource_viewer.is_dir is True
  assert resource_viewer.content is None
  assert len(resource_viewer.children) == 3

  # dir with a dir
  assert resource_viewer.children[0].name == "dir_root_1"
  assert resource_viewer.children[0].element_rel_path == 'dir_root_1'
  assert resource_viewer.children[0].is_dir is True
  assert resource_viewer.children[0].content is None
  assert len(resource_viewer.children[0].children) == 1

  # dir with files
  assert resource_viewer.children[0].children[0].name == "dir_root_1_0"
  assert resource_viewer.children[0].children[0].element_rel_path == 'dir_root_1/dir_root_1_0'
  assert resource_viewer.children[0].children[0].is_dir is True
  assert resource_viewer.children[0].children[0].content is None
  assert len(resource_viewer.children[0].children[0].children) == 2

  # empty file
  assert resource_viewer.children[0].children[0].children[0].name == "file_root_1_0_1.txt"
  assert resource_viewer.children[0].children[0].children[0].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_1.txt'
  assert resource_viewer.children[0].children[0].children[0].is_dir is False
  assert resource_viewer.children[0].children[0].children[0].content == FILE_2_CONTENT
  assert len(resource_viewer.children[0].children[0].children[0].children) == 0

  # file with content
  assert resource_viewer.children[0].children[0].children[1].name == "file_root_1_0_0.txt"
  assert resource_viewer.children[0].children[0].children[1].element_rel_path == 'dir_root_1/dir_root_1_0/file_root_1_0_0.txt'
  assert resource_viewer.children[0].children[0].children[1].is_dir is False
  assert resource_viewer.children[0].children[0].children[1].content == FILE_1_CONTENT
  assert len(resource_viewer.children[0].children[0].children[1].children) == 0

  # file in root dir
  assert resource_viewer.children[1].name == "file_root_0.txt"
  assert resource_viewer.children[1].element_rel_path == 'file_root_0.txt'
  assert resource_viewer.children[1].is_dir is False
  assert resource_viewer.children[1].content == FILE_0_CONTENT
  assert len(resource_viewer.children[1].children) == 0

  # empty dir
  assert resource_viewer.children[2].name == "dir_root_0"
  assert resource_viewer.children[2].element_rel_path == 'dir_root_0'
  assert resource_viewer.children[2].is_dir is True
  assert resource_viewer.children[2].content is None
  assert len(resource_viewer.children[2].children) == 0

def test_ResourceWriter_constructor_with_default_values(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  assert resource_writer.output_dir_abs_path == str(dir_output)
  assert resource_writer.resources == {}

def test_ResourceWriter_store_resource_multiple(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  resource_writer.store_resource('key_1', 'key_2', 'key_3', 'resource body 1')
  resource_writer.store_resource('key_1', 'key_2', 'key_4', 'resource body 2')
  resource_writer.store_resource('key_1', 'key_5', 'key_3', 'resource body 3')
  resource_writer.store_resource('key_6', 'key_2', 'key_3', 'resource body 4')
  resource_writer.store_resource('key_7', 'key_8', 'key_9', 'resource body 5')

  assert len(resource_writer.resources) == 5
  assert ('key_1', 'key_2', 'key_3') in resource_writer.resources
  assert resource_writer.resources[('key_1', 'key_2', 'key_3')] == 'resource body 1'
  assert ('key_1', 'key_2', 'key_4') in resource_writer.resources
  assert resource_writer.resources[('key_1', 'key_2', 'key_4')] == 'resource body 2'
  assert ('key_1', 'key_5', 'key_3') in resource_writer.resources
  assert resource_writer.resources[('key_1', 'key_5', 'key_3')] == 'resource body 3'
  assert ('key_6', 'key_2', 'key_3') in resource_writer.resources
  assert resource_writer.resources[('key_6', 'key_2', 'key_3')] == 'resource body 4'
  assert ('key_7', 'key_8', 'key_9') in resource_writer.resources
  assert resource_writer.resources[('key_7', 'key_8', 'key_9')] == 'resource body 5'

def test_ResourceWriter_store_resource_duplicate(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  resource_writer.store_resource('key_1', 'key_2', 'key_3', 'resource body 1')
  with pytest.raises(Exception):
      resource_writer.store_resource('key_1', 'key_2', 'key_3', 'resource body 1')
  assert 'Resource (key_1, key_2, key_3) already exists' in caplog.text

def test_ResourceWriter_store_resource_undefined_dir_rel_path(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  with pytest.raises(Exception):
    resource_writer.store_resource(None, 'key_2', 'key_3', 'resource body 1')
  assert 'Parameter `dir_rel_path` is undefined' in caplog.text

  with pytest.raises(Exception):
    resource_writer.store_resource('', 'key_2', 'key_3', 'resource body 1')
  assert 'Parameter `dir_rel_path` is undefined' in caplog.text

def test_ResourceWriter_store_resource_undefined_resource_kind(tmp_path, caplog):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  with pytest.raises(Exception):
    resource_writer.store_resource('key_1', None, 'key_3', 'resource body 1')
  assert 'Parameter `resource_kind` is undefined' in caplog.text

  with pytest.raises(Exception):
    resource_writer.store_resource('key_1', '', 'key_3', 'resource body 1')
  assert 'Parameter `resource_kind` is undefined' in caplog.text

def test_ResourceWriter_assemble_filename(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  assert resource_writer._assemble_filename('key_1', 'key_2') == 'key_1_key_2.yml'
  assert resource_writer._assemble_filename('Key_1', 'Key_2') == 'Key_1_Key_2.yml'

def test_ResourceWriter_assemble_filename_undefined_resource_name(tmp_path):
  dir_output = tmp_path / 'dir_output'
  dir_output.mkdir()
  resource_writer = ResourceWriter(str(dir_output))

  assert resource_writer._assemble_filename('key_1', None) == 'key_1.yml'
  assert resource_writer._assemble_filename('Key_1', None) == 'key_1.yml'

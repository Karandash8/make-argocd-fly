import pytest
from make_argocd_fly.config import get_abs_path, read_config, Config


def test_get_abs_path_with_relative_path_in_current_directory(tmp_path):
  root_dir = tmp_path
  path = 'config.py'
  expected = tmp_path / 'config.py'
  expected.write_text('test')

  assert get_abs_path(root_dir, path) == str(expected)

def test_get_abs_path_with_absolute_path_in_current_directory(tmp_path):
  root_dir = tmp_path
  path = tmp_path / 'config.py'
  expected = tmp_path / 'config.py'
  expected.write_text('test')

  assert get_abs_path(root_dir, path) == expected

def test_get_abs_path_with_relative_path_in_subdirectory(tmp_path):
  root_dir = tmp_path
  src_dir = tmp_path / 'source'
  src_dir.mkdir()
  path = 'source/app.py'
  expected = tmp_path / 'source/app.py'
  expected.write_text('test')

  assert get_abs_path(str(root_dir), path) == str(expected)

def test_get_abs_path_with_absolute_path_in_subdirectory(tmp_path):
  root_dir = tmp_path
  src_dir = tmp_path / 'source'
  src_dir.mkdir()
  path = tmp_path / 'source/app.py'
  expected = tmp_path / 'source/app.py'
  expected.write_text('test')

  assert get_abs_path(root_dir, path) == expected

def test_get_abs_path_with_empty_path(tmp_path, caplog):
  root_dir = tmp_path
  path = ''

  with pytest.raises(Exception):
    get_abs_path(root_dir, path)
  assert 'Path is empty.' in caplog.text

def test_get_abs_path_with_none_path(tmp_path, caplog):
  root_dir = tmp_path
  path = None

  with pytest.raises(Exception):
    get_abs_path(root_dir, path)
  assert 'Path is empty.' in caplog.text

def test_get_abs_path_with_nonexistent_path(tmp_path, caplog):
  root_dir = str(tmp_path)
  path = 'nonexistent_file.py'
  non_existent_path = tmp_path / 'nonexistent_file.py'

  with pytest.raises(Exception):
    get_abs_path(root_dir, path)
  assert 'Path does not exist: {}'.format(non_existent_path) in caplog.text

def test_get_abs_path_with_nonexistent_path_allow_missing(tmp_path, caplog):
  root_dir = str(tmp_path)
  path = 'nonexistent_file.py'
  non_existent_path = tmp_path / 'nonexistent_file.py'

  assert get_abs_path(root_dir, path, allow_missing=True) == str(non_existent_path)


##################
### Config
##################

def test_read_config_with_valid_config_file(tmp_path):
  root_dir = tmp_path
  config_file = 'config.yml'
  source_dir = 'source'
  output_dir = 'output'
  tmp_dir = '.tmp'
  config_file_path = tmp_path / config_file
  config_file_path.write_text('test')
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()
  config = read_config(root_dir, config_file, source_dir, output_dir, tmp_dir)
  assert isinstance(config, Config)
  assert config.get_source_dir() == str(source_dir_path)

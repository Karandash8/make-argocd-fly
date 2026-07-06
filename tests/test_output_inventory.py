import os

import pytest

from make_argocd_fly.output_inventory import FileRecord, OutputInventory, scan_output_scope, scan_output_scopes


def test_scan_output_scope__missing_output_directory_returns_empty(tmp_path):
  output_dir = tmp_path / 'output'

  inventory = scan_output_scope(str(output_dir))

  assert isinstance(inventory, OutputInventory)
  assert inventory.files == {}


def test_scan_output_scope__missing_scoped_directory_returns_empty(tmp_path):
  output_dir = tmp_path / 'output'
  output_dir.mkdir()

  inventory = scan_output_scope(str(output_dir), 'dev/app1')

  assert inventory.files == {}


def test_scan_output_scope__empty_output_directory_returns_empty(tmp_path):
  output_dir = tmp_path / 'output'
  output_dir.mkdir()

  inventory = scan_output_scope(str(output_dir))

  assert inventory.files == {}


def test_scan_output_scope__whole_output_scan_finds_nested_files(tmp_path):
  output_dir = tmp_path / 'output'
  app_dir = output_dir / 'dev' / 'app1'
  app_dir.mkdir(parents=True)
  deployment = app_dir / 'deployment.yaml'
  service = app_dir / 'service.yaml'
  deployment.write_text('kind: Deployment')
  service.write_text('kind: Service')

  inventory = scan_output_scope(str(output_dir))

  assert sorted(inventory.files.keys()) == ['dev/app1/deployment.yaml', 'dev/app1/service.yaml']

  deployment_stat = deployment.stat()
  record = inventory.files['dev/app1/deployment.yaml']
  assert isinstance(record, FileRecord)
  assert record.rel_path == 'dev/app1/deployment.yaml'
  assert record.abs_path == str(deployment)
  assert record.size == deployment_stat.st_size
  assert record.mtime_ns == deployment_stat.st_mtime_ns


def test_scan_output_scope__scoped_scan_returns_output_root_relative_paths(tmp_path):
  output_dir = tmp_path / 'output'
  app_dir = output_dir / 'dev' / 'app1'
  app_dir.mkdir(parents=True)
  (app_dir / 'deployment.yaml').write_text('kind: Deployment')
  (app_dir / 'service.yaml').write_text('kind: Service')

  inventory = scan_output_scope(str(output_dir), 'dev/app1')

  assert sorted(inventory.files.keys()) == ['dev/app1/deployment.yaml', 'dev/app1/service.yaml']
  assert 'deployment.yaml' not in inventory.files
  assert 'service.yaml' not in inventory.files


def test_scan_output_scope__scoped_scan_excludes_sibling_apps(tmp_path):
  output_dir = tmp_path / 'output'
  app1_dir = output_dir / 'dev' / 'app1'
  app2_dir = output_dir / 'dev' / 'app2'
  app1_dir.mkdir(parents=True)
  app2_dir.mkdir(parents=True)
  (app1_dir / 'deployment.yaml').write_text('kind: Deployment')
  (app2_dir / 'deployment.yaml').write_text('kind: Deployment')

  inventory = scan_output_scope(str(output_dir), 'dev/app1')

  assert sorted(inventory.files.keys()) == ['dev/app1/deployment.yaml']


def test_scan_output_scopes__multiple_scopes_merge_into_one_inventory(tmp_path):
  output_dir = tmp_path / 'output'
  app1_dir = output_dir / 'dev' / 'app1'
  app2_dir = output_dir / 'dev' / 'app2'
  app1_dir.mkdir(parents=True)
  app2_dir.mkdir(parents=True)
  (app1_dir / 'deployment.yaml').write_text('kind: Deployment')
  (app2_dir / 'service.yaml').write_text('kind: Service')

  inventory = scan_output_scopes(str(output_dir), ['dev/app1', 'dev/app2'])

  assert sorted(inventory.files.keys()) == ['dev/app1/deployment.yaml', 'dev/app2/service.yaml']


def test_scan_output_scopes__empty_scope_list_returns_empty_inventory(tmp_path):
  output_dir = tmp_path / 'output'
  output_dir.mkdir()

  inventory = scan_output_scopes(str(output_dir), [])

  assert inventory.files == {}


def test_scan_output_scope__does_not_read_file_contents(tmp_path, monkeypatch):
  output_dir = tmp_path / 'output'
  output_dir.mkdir()
  (output_dir / 'deployment.yaml').write_text('kind: Deployment')

  def fail_open(*args, **kwargs):
    raise AssertionError('scanner must not read file contents')

  monkeypatch.setattr('builtins.open', fail_open)

  inventory = scan_output_scope(str(output_dir))

  assert sorted(inventory.files.keys()) == ['deployment.yaml']


def test_scan_output_scope__symlink_directories_are_not_followed(tmp_path):
  if not hasattr(os, 'symlink'):
    pytest.skip('os.symlink is unavailable')

  output_dir = tmp_path / 'output'
  app1_dir = output_dir / 'dev' / 'app1'
  linked_dir = tmp_path / 'linked'
  app1_dir.mkdir(parents=True)
  linked_dir.mkdir()
  (app1_dir / 'deployment.yaml').write_text('kind: Deployment')
  (linked_dir / 'secret.yaml').write_text('kind: Secret')

  try:
    os.symlink(str(linked_dir), str(app1_dir / 'linked'))
  except OSError:
    pytest.skip('directory symlinks are unavailable')

  inventory = scan_output_scope(str(output_dir), 'dev/app1')

  assert sorted(inventory.files.keys()) == ['dev/app1/deployment.yaml']


def test_scan_output_scope__symlink_scope_outside_output_is_not_followed(tmp_path):
  if not hasattr(os, 'symlink'):
    pytest.skip('os.symlink is unavailable')

  output_dir = tmp_path / 'output'
  linked_dir = tmp_path / 'linked'
  output_dir.mkdir()
  linked_dir.mkdir()
  (linked_dir / 'secret.yaml').write_text('kind: Secret')

  try:
    os.symlink(str(linked_dir), str(output_dir / 'dev'))
  except OSError:
    pytest.skip('directory symlinks are unavailable')

  inventory = scan_output_scope(str(output_dir), 'dev')

  assert inventory.files == {}


def test_scan_output_scope__intermediate_symlink_scope_outside_output_is_not_followed(tmp_path):
  if not hasattr(os, 'symlink'):
    pytest.skip('os.symlink is unavailable')

  output_dir = tmp_path / 'output'
  linked_dir = tmp_path / 'linked'
  linked_app_dir = linked_dir / 'app1'
  output_dir.mkdir()
  linked_app_dir.mkdir(parents=True)
  (linked_app_dir / 'secret.yaml').write_text('kind: Secret')

  try:
    os.symlink(str(linked_dir), str(output_dir / 'dev'))
  except OSError:
    pytest.skip('directory symlinks are unavailable')

  inventory = scan_output_scope(str(output_dir), 'dev/app1')

  assert inventory.files == {}

import pytest

from make_argocd_fly.application import application_factory, Application, KustomizeApplication, AppOfApps
from make_argocd_fly.resource import ResourceViewer


def test_application_factory_create_Application(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'resource.yml'
  file_app.write_text(FILE_CONTENT)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  app_name = 'app'
  env_name = 'env'

  app_instance = application_factory(resource_viewer, app_name, env_name)

  assert isinstance(app_instance, Application)

def test_application_factory_create_KustomizeApplication(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'kustomization.yml'
  file_app.write_text(FILE_CONTENT)

  resource_viewer = ResourceViewer(str(dir_root))
  resource_viewer.build()

  app_name = 'app'
  env_name = 'env'

  app_instance = application_factory(resource_viewer, app_name, env_name)

  assert isinstance(app_instance, KustomizeApplication)

def test_application_factory_create_AppOfApps(tmp_path):
  app_name = 'app'
  env_name = 'env'

  app_instance = application_factory(None, app_name, env_name)

  assert isinstance(app_instance, AppOfApps)

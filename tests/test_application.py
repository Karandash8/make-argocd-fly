import pytest

from make_argocd_fly.application import application_factory, AppOfAppsApplication, SimpleApplication, KustomizeApplication


@pytest.mark.asyncio
async def test_application_factory_create_SimpleApplication(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'resource.yml'
  file_app.write_text(FILE_CONTENT)

  env_name = 'env'
  app_name = 'app'

  app_instance = await application_factory(env_name, app_name, str(dir_app))
  assert isinstance(app_instance, SimpleApplication)

@pytest.mark.asyncio
async def test_application_factory_create_KustomizeApplication(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'kustomization.yml'
  file_app.write_text(FILE_CONTENT)

  env_name = 'env'
  app_name = 'app'

  app_instance = await application_factory(env_name, app_name, str(dir_app))
  assert isinstance(app_instance, KustomizeApplication)

@pytest.mark.asyncio
async def test_application_factory_create_AppOfApps():
  env_name = 'env'
  app_name = 'app'

  app_instance = await application_factory(env_name, app_name, 'non_existing_dir')
  assert isinstance(app_instance, AppOfAppsApplication)

import pytest

from make_argocd_fly.application import workflow_factory, AppOfAppsWorkflow, SimpleWorkflow, KustomizeWorkflow


@pytest.mark.asyncio
async def test_workflow_factory_create_SimpleWorkflow(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'resource.yml'
  file_app.write_text(FILE_CONTENT)

  app_name = 'app'
  env_name = 'env'

  app_instance = await workflow_factory(app_name, env_name, str(dir_app))
  assert isinstance(app_instance, SimpleWorkflow)

@pytest.mark.asyncio
async def test_workflow_factory_create_KustomizeWorkflow(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'kustomization.yml'
  file_app.write_text(FILE_CONTENT)

  app_name = 'app'
  env_name = 'env'

  app_instance = await workflow_factory(app_name, env_name, str(dir_app))
  assert isinstance(app_instance, KustomizeWorkflow)

@pytest.mark.asyncio
async def test_application_factory_create_AppOfApps():
  app_name = 'app'
  env_name = 'env'

  app_instance = await workflow_factory(app_name, env_name, 'non_existing_dir')
  assert isinstance(app_instance, AppOfAppsWorkflow)

import pytest

from make_argocd_fly.pipeline import build_pipeline
from make_argocd_fly.const import ApplicationType
from make_argocd_fly.context import Context


def test_application_factory_create_SimpleApplication(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'resource.yml'
  file_app.write_text(FILE_CONTENT)

  env_name = 'env'
  app_name = 'app'

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, str(dir_app))
  assert pipeline.type == ApplicationType.K8S_SIMPLE

def test_application_factory_create_KustomizeApplication(tmp_path):
  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / 'app'
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'kustomization.yml'
  file_app.write_text(FILE_CONTENT)

  env_name = 'env'
  app_name = 'app'

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, str(dir_app))
  assert pipeline.type == ApplicationType.K8S_KUSTOMIZE

def test_application_factory_create_AppOfApps():
  env_name = 'env'
  app_name = 'app'

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, 'non_existing_dir')
  assert pipeline.type == ApplicationType.K8S_APP_OF_APPS

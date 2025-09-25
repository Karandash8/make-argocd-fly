import pytest
from unittest.mock import MagicMock

from make_argocd_fly.pipeline import build_pipeline, PipelineType
from make_argocd_fly.context import Context
from make_argocd_fly.param import ApplicationTypes
from make_argocd_fly.exception import ConfigFileError


def test_build_pipeline__unknown_app_type(caplog, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = 'unknown_app_type'
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)

  env_name = 'env'
  app_name = 'app'

  ctx = Context(env_name, app_name)
  with pytest.raises(ConfigFileError) as excinfo:
    build_pipeline(ctx, 'non_existing_dir')

  assert str(excinfo.value) == 'Config file error'
  assert f'Unknown application type \'{mock_params.app_type}\' in application {ctx.app_name} in environment {ctx.env_name}. Valid types are: [\'k8s\', \'generic\']' in caplog.text

def test_build_pipeline__create_SimpleApplication(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.K8S.value
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)

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
  assert pipeline.type == PipelineType.K8S_SIMPLE

def test_build_pipeline__create_KustomizeApplication(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.K8S.value
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)

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
  assert pipeline.type == PipelineType.K8S_KUSTOMIZE

def test_build_pipeline__create_AppOfApps(mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.K8S.value
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)

  env_name = 'env'
  app_name = 'app'

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, 'non_existing_dir')
  assert pipeline.type == PipelineType.K8S_APP_OF_APPS

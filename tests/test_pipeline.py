import pytest
import asyncio
from unittest.mock import MagicMock

from make_argocd_fly.pipeline import build_pipeline, PipelineType
from make_argocd_fly.resource.viewer import build_scoped_viewer
from make_argocd_fly.context import Context
from make_argocd_fly.param import ApplicationTypes
from make_argocd_fly.exception import ConfigFileError
from make_argocd_fly.limits import RuntimeLimits


def test_build_pipeline__unknown_app_type(tmp_path, caplog, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = 'unknown_app_type'
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)
  limits = RuntimeLimits(
    app_sem=asyncio.Semaphore(1),
    subproc_sem=asyncio.Semaphore(1),
    io_sem=asyncio.Semaphore(1),
  )

  env_name = 'env'
  app_name = 'app'

  ctx = Context(env_name, app_name)
  with pytest.raises(ConfigFileError) as excinfo:
    build_pipeline(ctx, limits, build_scoped_viewer(tmp_path))

  assert str(excinfo.value) == 'Config file error'
  assert f'Unknown application type \'{mock_params.app_type}\' in application {ctx.app_name} in environment {ctx.env_name}. Valid types are: [\'k8s\', \'generic\']' in caplog.text

def test_build_pipeline__create_SimpleApplication(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.K8S
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)
  limits = RuntimeLimits(
    app_sem=asyncio.Semaphore(1),
    subproc_sem=asyncio.Semaphore(1),
    io_sem=asyncio.Semaphore(1),
  )

  env_name = 'env'
  app_name = 'app'

  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / app_name
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'resource.yml'
  file_app.write_text(FILE_CONTENT)

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, limits, build_scoped_viewer(dir_root))
  assert pipeline.type == PipelineType.K8S_SIMPLE

def test_build_pipeline__create_KustomizeApplication(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.K8S
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)
  limits = RuntimeLimits(
    app_sem=asyncio.Semaphore(1),
    subproc_sem=asyncio.Semaphore(1),
    io_sem=asyncio.Semaphore(1),
  )

  env_name = 'env'
  app_name = 'app'

  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / app_name
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'kustomization.yml'
  file_app.write_text(FILE_CONTENT)

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, limits, build_scoped_viewer(dir_root))
  assert pipeline.type == PipelineType.K8S_KUSTOMIZE

def test_build_pipeline__create_HelmfileApplication(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.K8S
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)
  limits = RuntimeLimits(
    app_sem=asyncio.Semaphore(1),
    subproc_sem=asyncio.Semaphore(1),
    io_sem=asyncio.Semaphore(1),
  )

  env_name = 'env'
  app_name = 'app'

  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / app_name
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'helmfile.yaml'
  file_app.write_text(FILE_CONTENT)

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, limits, build_scoped_viewer(dir_root))
  assert pipeline.type == PipelineType.K8S_HELMFILE

def test_build_pipeline__create_AppOfApps(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.K8S
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)
  limits = RuntimeLimits(
    app_sem=asyncio.Semaphore(1),
    subproc_sem=asyncio.Semaphore(1),
    io_sem=asyncio.Semaphore(1),
  )

  env_name = 'env'
  app_name = 'app'

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, limits, build_scoped_viewer(tmp_path))
  assert pipeline.type == PipelineType.K8S_APP_OF_APPS

def test_build_pipeline__create_GenericApplication(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.app_type = ApplicationTypes.GENERIC
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
  mocker.patch('make_argocd_fly.pipeline.get_config', mock_get_config)
  limits = RuntimeLimits(
    app_sem=asyncio.Semaphore(1),
    subproc_sem=asyncio.Semaphore(1),
    io_sem=asyncio.Semaphore(1),
  )

  env_name = 'env'
  app_name = 'app'

  dir_root = tmp_path / 'dir_root'
  dir_root.mkdir()
  dir_app = dir_root / app_name
  dir_app.mkdir()
  FILE_CONTENT = 'content'
  file_app = dir_app / 'file.txt'
  file_app.write_text(FILE_CONTENT)

  ctx = Context(env_name, app_name)
  pipeline = build_pipeline(ctx, limits, build_scoped_viewer(dir_root))
  assert pipeline.type == PipelineType.GENERIC

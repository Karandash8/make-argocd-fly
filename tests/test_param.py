import pytest
from make_argocd_fly.exception import ConfigFileError
from make_argocd_fly.param import Params, ApplicationTypes

##################
### Params.populate_params
##################

def test_Params__populate_params__empty() -> None:
  params = Params()
  params.populate_params()
  assert params.app_type == ApplicationTypes.K8S
  assert params.parent_app is None
  assert params.parent_app_env is None
  assert params.non_k8s_files_to_render == []
  assert params.exclude_rendering == []

def test_Params__populate_params__all() -> None:
  params = Params()
  params.populate_params(
    app_type='k8s',
    parent_app='test_app',
    parent_app_env='test_env',
    non_k8s_files_to_render=['file1', 'file2'],
    exclude_rendering=['file3', 'file4']
  )
  assert params.app_type == ApplicationTypes.K8S
  assert params.parent_app == 'test_app'
  assert params.parent_app_env == 'test_env'
  assert params.non_k8s_files_to_render == ['file1', 'file2']
  assert params.exclude_rendering == ['file3', 'file4']

def test_Params__populate_params__partial() -> None:
  params = Params()
  params.populate_params(
    parent_app='test_app',
    non_k8s_files_to_render=['file1']
  )
  assert params.app_type == ApplicationTypes.K8S
  assert params.parent_app == 'test_app'
  assert params.parent_app_env is None
  assert params.non_k8s_files_to_render == ['file1']
  assert params.exclude_rendering == []

def test_Params__populate_params__unknown_param(caplog) -> None:
  params = Params()

  with pytest.raises(ConfigFileError):
    params.populate_params(unknown_param='value')
  assert 'Unknown parameter "unknown_param" in Params' in caplog.text


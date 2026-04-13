import pytest
from make_argocd_fly.exception import ConfigFileError
from make_argocd_fly.param import Params, ApplicationTypes, ApplicationNameFormat

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
  assert params.kustomize_common_dirs == []
  assert params.application_name == ApplicationNameFormat.SHORT

def test_Params__populate_params__all() -> None:
  params = Params()
  params.populate_params(
    app_type='k8s',
    parent_app='test_app',
    parent_app_env='test_env',
    non_k8s_files_to_render=['file1', 'file2'],
    exclude_rendering=['file3', 'file4'],
    kustomize_common_dirs=['common', 'shared'],
    application_name='full'
  )
  assert params.app_type == ApplicationTypes.K8S
  assert params.parent_app == 'test_app'
  assert params.parent_app_env == 'test_env'
  assert params.non_k8s_files_to_render == ['file1', 'file2']
  assert params.exclude_rendering == ['file3', 'file4']
  assert params.kustomize_common_dirs == ['common', 'shared']
  assert params.application_name == ApplicationNameFormat.FULL

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
  assert params.kustomize_common_dirs == []
  assert params.application_name == ApplicationNameFormat.SHORT

def test_Params__populate_params__unknown_param(caplog) -> None:
  params = Params()

  with pytest.raises(ConfigFileError):
    params.populate_params(unknown_param='value')

def test_Params__populate_params__kustomize_common_dirs_single() -> None:
  params = Params()
  params.populate_params(kustomize_common_dirs=['common'])
  assert params.kustomize_common_dirs == ['common']

def test_Params__populate_params__kustomize_common_dirs_multiple() -> None:
  params = Params()
  params.populate_params(kustomize_common_dirs=['common', 'shared', 'base-patches'])
  assert params.kustomize_common_dirs == ['common', 'shared', 'base-patches']

def test_Params__populate_params__kustomize_common_dirs_empty_list() -> None:
  params = Params()
  params.populate_params(kustomize_common_dirs=[])
  assert params.kustomize_common_dirs == []

def test_Params__populate_params__kustomize_common_dirs_default_unchanged() -> None:
  # not passing kustomize_common_dirs should leave the default intact
  params = Params()
  params.populate_params(parent_app='test_app')
  assert params.kustomize_common_dirs == []

def test_Params__populate_params__kustomize_common_dirs_with_other_params() -> None:
  params = Params()
  params.populate_params(
    exclude_rendering=['prod'],
    kustomize_common_dirs=['common']
  )
  assert params.exclude_rendering == ['prod']
  assert params.kustomize_common_dirs == ['common']

def test_Params__populate_params__unknown_param_alongside_kustomize_common_dirs() -> None:
  params = Params()
  with pytest.raises(ConfigFileError):
    params.populate_params(kustomize_common_dirs=['common'], unknown_param='value')

def test_Params__populate_params__application_name_short() -> None:
  params = Params()
  params.populate_params(application_name='short')
  assert params.application_name == ApplicationNameFormat.SHORT

def test_Params__populate_params__application_name_full() -> None:
  params = Params()
  params.populate_params(application_name='full')
  assert params.application_name == ApplicationNameFormat.FULL

def test_Params__populate_params__application_name_default_unchanged() -> None:
  params = Params()
  params.populate_params(parent_app='test_app')
  assert params.application_name == ApplicationNameFormat.SHORT

def test_Params__populate_params__application_name_invalid() -> None:
  params = Params()
  with pytest.raises(ConfigFileError):
    params.populate_params(application_name='invalid_value')

def test_Params__populate_params__application_name_with_other_params() -> None:
  params = Params()
  params.populate_params(
    exclude_rendering=['prod'],
    application_name='full'
  )
  assert params.exclude_rendering == ['prod']
  assert params.application_name == ApplicationNameFormat.FULL

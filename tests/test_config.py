import pytest
import textwrap
from unittest.mock import MagicMock

from make_argocd_fly.config import populate_config, get_config, Config, _read_config_file, _list_config_files
from make_argocd_fly.exceptions import ConfigFileError, InternalError
from make_argocd_fly.utils import check_lists_equal


##################
### populate_config
##################

def test_populate_config__default_values(tmp_path):
  root_dir = tmp_path
  config_dir = 'config'
  source_dir = 'source'
  output_dir = 'output'
  tmp_dir = '.tmp'

  config_dir_path = tmp_path / config_dir
  config_dir_path.mkdir()

  config_file_path = config_dir_path / 'config.yml'
  config_file_path.write_text('vars: {}')

  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert isinstance(config, Config)
  assert config.source_dir == str(source_dir_path)
  assert config.output_dir == str(root_dir / output_dir)
  assert config.tmp_dir == str(root_dir / tmp_dir)

def test_populate_config__non_default_values(tmp_path):
  root_dir = tmp_path
  config_dir = 'config_new'
  config_file = 'config_new.yml'
  source_dir = 'source_new'
  output_dir = 'output_new'
  tmp_dir = '.tmp_new'

  config_dir_path = tmp_path / config_dir
  config_dir_path.mkdir()

  config_file_path = config_dir_path / config_file
  config_file_path.write_text('vars: {}')

  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir,
                           config_dir=config_dir,
                           source_dir=source_dir,
                           output_dir=output_dir,
                           tmp_dir=tmp_dir)

  assert isinstance(config, Config)
  assert config.source_dir == str(source_dir_path)
  assert config.output_dir == str(root_dir / output_dir)
  assert config.tmp_dir == str(root_dir / tmp_dir)

def test_populate_config__missing_source_dir(tmp_path):
  root_dir = tmp_path
  config_dir = 'config'
  config_file = 'config.yml'

  config_dir_path = tmp_path / config_dir
  config_dir_path.mkdir()

  config_file_path = config_dir_path / config_file
  config_file_path.write_text('vars: {}')

  with pytest.raises(InternalError):
    populate_config(root_dir=root_dir)

def test_populate_config__not_populated_config(tmp_path):
  config = Config()

  with pytest.raises(InternalError):
    config.source_dir

  with pytest.raises(InternalError):
    config.output_dir

  with pytest.raises(InternalError):
    config.tmp_dir

##################
### _list_config_files
##################

def test__list_config_files__empty_dir(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  with pytest.raises(InternalError):
    _list_config_files(config_dir)

def test__list_config_files__single_file(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text('test')

  assert _list_config_files(config_dir) == ['config.yml']

def test__list_config_files__multiple_files(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file1 = config_dir / 'config1.yml'
  config_file1.write_text('test')

  config_file2 = config_dir / 'config2.yml'
  config_file2.write_text('test')

  assert _list_config_files(config_dir) == ['config1.yml', 'config2.yml']

def test__list_config_files__non_yml_file(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.txt'
  config_file.write_text('test')

  with pytest.raises(InternalError):
    _list_config_files(config_dir)

def test__list_config_files__nested_dir(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  nested_dir = config_dir / 'nested'
  nested_dir.mkdir()

  config_file = nested_dir / 'config.yml'
  config_file.write_text('test')

  with pytest.raises(InternalError):
    _list_config_files(config_dir)

def test__list_config_files__mixed_files(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file1 = config_dir / 'config1.yml'
  config_file1.write_text('test')

  config_file2 = config_dir / 'config2.txt'
  config_file2.write_text('test')

  nested_dir = config_dir / 'nested'
  nested_dir.mkdir()

  config_file3 = nested_dir / 'config3.yml'
  config_file3.write_text('test')

  assert _list_config_files(config_dir) == ['config1.yml']

def test__list_config_files__non_existent_config_dir(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'

  with pytest.raises(InternalError):
    _list_config_files(config_dir)

##################
### _read_config_file
##################

def test__read_config_file__valid_config_file(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          bootstrap: {}
    '''

  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))

  expected_config = {
    'envs': {
      'test_env': {
        'apps': {
          'bootstrap': {}
        }
      }
    }
  }

  assert _read_config_file(config_file) == expected_config

def test__read_config_file__invalid_config_file(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          bootstrap: [
    '''

  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))

  with pytest.raises(ConfigFileError):
    _read_config_file(config_file)

def test__read_config_file__missing_config_file(tmp_path):
  root_dir = tmp_path
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'

  with pytest.raises(InternalError):
    _read_config_file(config_file)

##################
### Config.get_envs
##################

def test_Config__get_envs__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config.get_envs()
  assert 'Config is not populated' in caplog.text

def test_Config__get_envs__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
      test_env2: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_envs() == {'test_env': {}, 'test_env2': {}}

def test_Config__get_envs__not_valid_config(tmp_path):
  CONFIG = '''\
    not_envs:
      test_env: {}
      test_env2: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_envs() == {}

##################
### Config.get_global_vars
##################

def test_Config__get_global_vars__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config.get_global_vars()
  assert 'Config is not populated' in caplog.text

def test_Config__get_global_vars__valid_config(tmp_path):
  CONFIG = '''\
    vars:
      test_var: var
      test_var2: var
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_global_vars() == {'test_var': 'var', 'test_var2': 'var'}

def test_Config__get_global_vars__not_valid_config(tmp_path):
  CONFIG = '''\
    not_vars:
      test_var: var
      test_var2: var
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_global_vars() == {}

##################
### Config.get_env_vars
##################

def test_Config__get_env_vars__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        vars:
          test_var: var
          test_var2: var
      test_env2:
        vars:
          test_var3: var
          test_var4: var
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_env_vars('test_env') == {'test_var': 'var', 'test_var2': 'var'}
  assert config.get_env_vars('test_env2') == {'test_var3': 'var', 'test_var4': 'var'}

def test_Config__get_env_vars__undefined_vars(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_env_vars('test_env') == {}

def test_Config__get_env_vars__missing_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_env_vars('test_env2')

##################
### Config.get_app_vars
##################

def test_Config__get_app_vars__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app:
            vars:
              test_var: var
              test_var2: var
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_app_vars('test_env', 'test_app') == {'test_var': 'var', 'test_var2': 'var'}

def test_Config__get_app_vars__missing_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_vars('test_env2', 'test_app')

def test_Config__get_app_vars__undefined_apps(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_vars('test_env', 'test_app')

def test_Config__get_app_vars__missing_app(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_vars('test_env', 'test_app2')

def test_Config__get_app_vars__undefined_vars(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_app_vars('test_env', 'test_app') == {}

##################
### Config._get_global_params
##################

def test_Config___get_global_params__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config._get_global_params()
  assert 'Config is not populated' in caplog.text

def test_Config___get_global_params__valid_config(tmp_path):
  CONFIG = '''\
    params:
      test_params: var
      test_params2: var
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config._get_global_params() == {'test_params': 'var', 'test_params2': 'var'}

def test_Config___get_global_params__not_valid_config(tmp_path):
  CONFIG = '''\
    not_params:
      test_params: var
      test_params2: var
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config._get_global_params() == {}

##################
### Config._get_env_params
##################

def test_Config___get_env_params__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        params:
          test_param: param
          test_param2: param
      test_env2:
        params:
          test_param3: param
          test_param4: param
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config._get_env_params('test_env') == {'test_param': 'param', 'test_param2': 'param'}
  assert config._get_env_params('test_env2') == {'test_param3': 'param', 'test_param4': 'param'}

def test_Config___get_env_params__undefined_params(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config._get_env_params('test_env') == {}

def test_Config___get_env_params__missing_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config._get_env_params('test_env2')

##################
### Config._get_app_params
##################

def test_Config___get_app_params__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app:
            params:
              test_param: param
              test_param2: param
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config._get_app_params('test_env', 'test_app') == {'test_param': 'param', 'test_param2': 'param'}

def test_Config___get_app_params__missing_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config._get_app_params('test_env2', 'test_app')

def test_Config___get_app_params__undefined_apps(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config._get_app_params('test_env', 'test_app')

def test_Config___get_app_params__missing_app(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config._get_app_params('test_env', 'test_app2')

def test_Config___get_app_params__undefined_params(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config._get_app_params('test_env', 'test_app') == {}

##################
### Config.get_params
##################

def test_Config__get_params__empty_up_to_global(mocker):
  global_params_return_value = {}
  env_params_return_value = {}
  app_params_return_value = {}

  with mocker.patch('make_argocd_fly.config.Config._get_global_params', return_value=global_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_env_params', return_value=env_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_app_params', return_value=app_params_return_value):

    params = get_config().get_params()
    assert params.parent_app is None
    assert params.parent_app_env is None
    assert check_lists_equal(params.non_k8s_files_to_render, [])
    assert check_lists_equal(params.exclude_rendering, [])

def test_Config__get_params__empty_up_to_env(mocker):
  global_params_return_value = {}
  env_params_return_value = {}
  app_params_return_value = {}

  with mocker.patch('make_argocd_fly.config.Config._get_global_params', return_value=global_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_env_params', return_value=env_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_app_params', return_value=app_params_return_value):

    params = get_config().get_params(env_name='test_env')
    assert params.parent_app is None
    assert params.parent_app_env is None
    assert check_lists_equal(params.non_k8s_files_to_render, [])
    assert check_lists_equal(params.exclude_rendering, [])

def test_Config__get_params__empty_up_to_app(mocker):
  global_params_return_value = {}
  env_params_return_value = {}
  app_params_return_value = {}

  with mocker.patch('make_argocd_fly.config.Config._get_global_params', return_value=global_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_env_params', return_value=env_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_app_params', return_value=app_params_return_value):

    params = get_config().get_params(env_name='test_env', app_name='test_app')
    assert params.parent_app is None
    assert params.parent_app_env is None
    assert check_lists_equal(params.non_k8s_files_to_render, [])
    assert check_lists_equal(params.exclude_rendering, [])

def test_Config__get_params__global_only(mocker):
  global_params_return_value = {'parent_app': 'parent_app_value',
                                'parent_app_env': 'parent_app_env_value',
                                'non_k8s_files_to_render': ['file1', 'file2'],
                                'exclude_rendering': ['exclude1', 'exclude2']}
  env_params_return_value = {}
  app_params_return_value = {}

  with mocker.patch('make_argocd_fly.config.Config._get_global_params', return_value=global_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_env_params', return_value=env_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_app_params', return_value=app_params_return_value):

    params = get_config().get_params(env_name='test_env', app_name='test_app')
    assert params.parent_app == 'parent_app_value'
    assert params.parent_app_env == 'parent_app_env_value'
    assert check_lists_equal(params.non_k8s_files_to_render, ['file1', 'file2'])
    assert check_lists_equal(params.exclude_rendering, ['exclude1', 'exclude2'])

def test_Config__get_params__env_override(mocker):
  global_params_return_value = {'parent_app': 'parent_app_value',
                                'parent_app_env': 'parent_app_env_value',
                                'non_k8s_files_to_render': ['file1', 'file2'],
                                'exclude_rendering': ['exclude1', 'exclude2']}
  env_params_return_value = {'parent_app': 'env_parent_app_value',
                             'parent_app_env': 'env_parent_app_env_value',
                             'non_k8s_files_to_render': ['env_file1', 'env_file2'],
                             'exclude_rendering': ['env_exclude1', 'env_exclude2']}
  app_params_return_value = {}

  with mocker.patch('make_argocd_fly.config.Config._get_global_params', return_value=global_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_env_params', return_value=env_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_app_params', return_value=app_params_return_value):

    params = get_config().get_params(env_name='test_env', app_name='test_app')
    assert params.parent_app == 'env_parent_app_value'
    assert params.parent_app_env == 'env_parent_app_env_value'
    assert check_lists_equal(params.non_k8s_files_to_render, ['env_file1', 'env_file2'])
    assert check_lists_equal(params.exclude_rendering, ['env_exclude1', 'env_exclude2'])

def test_Config__get_params__app_override(mocker):
  global_params_return_value = {'parent_app': 'parent_app_value',
                                'parent_app_env': 'parent_app_env_value',
                                'non_k8s_files_to_render': ['file1', 'file2'],
                                'exclude_rendering': ['exclude1', 'exclude2']}
  env_params_return_value = {'parent_app': 'env_parent_app_value',
                             'parent_app_env': 'env_parent_app_env_value',
                             'non_k8s_files_to_render': ['env_file1', 'env_file2'],
                             'exclude_rendering': ['env_exclude1', 'env_exclude2']}
  app_params_return_value = {'parent_app': 'app_parent_app_value',
                             'parent_app_env': 'app_parent_app_env_value',
                             'non_k8s_files_to_render': ['app_file1', 'app_file2'],
                             'exclude_rendering': ['app_exclude1', 'app_exclude2']}

  with mocker.patch('make_argocd_fly.config.Config._get_global_params', return_value=global_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_env_params', return_value=env_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_app_params', return_value=app_params_return_value):

    params = get_config().get_params(env_name='test_env', app_name='test_app')
    assert params.parent_app == 'app_parent_app_value'
    assert params.parent_app_env == 'app_parent_app_env_value'
    assert check_lists_equal(params.non_k8s_files_to_render, ['app_file1', 'app_file2'])
    assert check_lists_equal(params.exclude_rendering, ['app_exclude1', 'app_exclude2'])

def test_Config__get_params__random(mocker):
  global_params_return_value = {'parent_app': 'parent_app_value',
                                'non_k8s_files_to_render': ['file1', 'file2'],
                                'exclude_rendering': ['exclude1', 'exclude2']}
  env_params_return_value = {'non_k8s_files_to_render': ['env_file1', 'env_file2'],
                             'exclude_rendering': ['env_exclude1', 'env_exclude2']}
  app_params_return_value = {'exclude_rendering': ['app_exclude1', 'app_exclude2']}

  with mocker.patch('make_argocd_fly.config.Config._get_global_params', return_value=global_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_env_params', return_value=env_params_return_value), \
       mocker.patch('make_argocd_fly.config.Config._get_app_params', return_value=app_params_return_value):

    params = get_config().get_params(env_name='test_env', app_name='test_app')
    assert params.parent_app == 'parent_app_value'
    assert params.parent_app_env is None
    assert check_lists_equal(params.non_k8s_files_to_render, ['env_file1', 'env_file2'])
    assert check_lists_equal(params.exclude_rendering, ['app_exclude1', 'app_exclude2'])

##################
### Config.get_app_params_deprecated
##################

def test_Config__get_app_params_deprecated__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app:
            param: param
            param2: param
            vars: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_app_params_deprecated('test_env', 'test_app') == {'param': 'param', 'param2': 'param'}

def test_Config__get_app_params_deprecated__missing_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_params_deprecated('test_env2', 'test_app')

def test_Config__get_app_params_deprecated__undefined_apps(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_params_deprecated('test_env', 'test_app')

def test_Config__get_app_params_deprecated__missing_app(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_params_deprecated('test_env', 'test_app2')


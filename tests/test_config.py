import pytest
import textwrap
from unittest.mock import MagicMock

from make_argocd_fly.config import populate_config, get_config, Config, ConfigKeywords
from make_argocd_fly.exception import ConfigFileError, InternalError
from make_argocd_fly.util import check_lists_equal


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
### Config.list_envs
##################

def test_Config__list_envs__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config.list_envs()
  assert 'Config is not populated' in caplog.text

def test_Config__list_envs__valid_config(tmp_path):
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

  expected_envs = ['test_env', 'test_env2']

  assert check_lists_equal(config.list_envs(), expected_envs)

def test_Config__list_envs__missing_envs_keyword(tmp_path, caplog):
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

  assert check_lists_equal(config.list_envs(), [])
  assert 'Missing `envs` keyword in config' in caplog.text

##################
### Config.get_env
##################

def test_Config__get_env__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config.get_env('test_env')
  assert 'Config is not populated' in caplog.text

def test_Config__get_env__valid_config(tmp_path):
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

  assert config.get_env('test_env') == {}
  assert config.get_env('test_env2') == {}

def test_Config__get_env__undefined_env(tmp_path, caplog):
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

  with pytest.raises(ConfigFileError):
    config.get_env('test_env3')
  assert 'Environment test_env3 is not defined' in caplog.text

##################
### Config.list_apps
##################

def test_Config__list_apps__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config.list_apps('test_env')
  assert 'Config is not populated' in caplog.text

def test_Config__list_apps__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          app1: {}
          app2: {}
      test_env2:
        apps:
          app3: {}
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

  assert check_lists_equal(config.list_apps('test_env'), ['app1', 'app2'])
  assert check_lists_equal(config.list_apps('test_env2'), ['app3'])

def test_Config__list_apps__missing_apps_keyword(tmp_path, caplog):
  CONFIG = '''\
    envs:
      test_env:
        not_apps: {}
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

  assert check_lists_equal(config.list_apps('test_env'), [])
  assert 'Missing `apps` keyword in environment test_env' in caplog.text

##################
### Config.get_app
##################

def test_Config__get_app__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config.get_app('test_env', 'app1')
  assert 'Config is not populated' in caplog.text

def test_Config__get_app__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          app1: {}
          app2: {}
      test_env2:
        apps:
          app3: {}
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

  assert config.get_app('test_env', 'app1') == {}
  assert config.get_app('test_env', 'app2') == {}
  assert config.get_app('test_env2', 'app3') == {}

def test_Config__get_app__undefined_app(tmp_path, caplog):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          app1: {}
          app2: {}
      test_env2:
        apps:
          app3: {}
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
    config.get_app('test_env', 'app3')
  assert 'Application app3 is not defined in environment test_env' in caplog.text

##################
### Config._get_global_scope
##################

def test_Config___get_global_scope__config_not_populated(tmp_path, caplog):
  config = Config()

  with pytest.raises(InternalError):
    config._get_global_scope(ConfigKeywords.VARS)
  assert 'Config is not populated' in caplog.text

def test_Config___get_global_scope__valid_config(tmp_path):
  CONFIG = '''\
    vars:
      test: var
      test2: var
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

  assert config._get_global_scope(ConfigKeywords.VARS) == {'test': 'var', 'test2': 'var'}

def test_Config___get_global_scope__not_valid_config(tmp_path):
  CONFIG = '''\
    not_vars:
      test: var
      test2: var
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

  assert config._get_global_scope(ConfigKeywords.VARS) == {}

##################
### Config._get_env_scope
##################

def test_Config___get_env_scope__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        vars:
          test: var
          test2: var
      test_env2:
        vars:
          test3: var
          test4: var
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

  assert config._get_env_scope(ConfigKeywords.VARS, 'test_env') == {'test': 'var', 'test2': 'var'}
  assert config._get_env_scope(ConfigKeywords.VARS, 'test_env2') == {'test3': 'var', 'test4': 'var'}

def test_Config___get_env_scope__undefined_scope(tmp_path):
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

  assert config._get_env_scope(ConfigKeywords.VARS, 'test_env') == {}

def test_Config___get_env_scope__missing_env(tmp_path):
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
    config._get_env_scope(ConfigKeywords.VARS, 'test_env2')

##################
### Config._get_app_scope
##################

def test_Config___get_app_scope__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app:
            vars:
              test: var
              test2: var
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

  assert config._get_app_scope(ConfigKeywords.VARS, 'test_env', 'test_app') == {'test': 'var', 'test2': 'var'}

def test_Config___get_app_scope__missing_env(tmp_path):
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
    config._get_app_scope(ConfigKeywords.VARS, 'test_env2', 'test_app')

def test_Config___get_app_scope__undefined_apps(tmp_path):
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
    config._get_app_scope(ConfigKeywords.VARS, 'test_env', 'test_app')

def test_Config___get_app_scope__missing_app(tmp_path, caplog):
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
    config._get_app_scope(ConfigKeywords.VARS, 'test_env', 'test_app2')
  assert 'Application test_app2 is not defined in environment test_env' in caplog.text

def test_Config___get_app_scope__undefined_vars(tmp_path):
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

  assert config._get_app_scope(ConfigKeywords.VARS, 'test_env', 'test_app') == {}

##################
### Config.get_vars
##################

def test_Config__get_vars__empty_up_to_global(mocker):
  global_vars_return_value = {}
  env_vars_return_value = {}
  app_vars_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {}
  vars = get_config().get_vars()
  assert vars == expected_vars

def test_Config__get_vars__empty_up_to_env(mocker):
  global_vars_return_value = {}
  env_vars_return_value = {}
  app_vars_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {}
  vars = get_config().get_vars(env_name='test_env')
  assert vars == expected_vars

def test_Config__get_vars__empty_up_to_app(mocker):
  global_vars_return_value = {}
  env_vars_return_value = {}
  app_vars_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {}
  vars = get_config().get_vars(env_name='test_env', app_name='test_app')
  assert vars == expected_vars

def test_Config__get_vars__extra_vars(mocker):
  extra_vars = {
    'var1': 'value_extra1',
    'var2': 'value_extra2'
  }
  global_vars_return_value = {}
  env_vars_return_value = {}
  app_vars_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'var1': 'value_extra1',
    'var2': 'value_extra2'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__global_only(mocker):
  extra_vars = {}
  global_vars_return_value = {
    'var1': 'value_global1',
    'var2': 'value_global2'
  }
  env_vars_return_value = {}
  app_vars_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'var1': 'value_global1',
    'var2': 'value_global2'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__extra_with_global_override(mocker):
  extra_vars = {
    'var1': 'value_extra1'
  }
  global_vars_return_value = {
    'var1': 'value_global1',
    'var2': 'value_global2'
  }
  env_vars_return_value = {}
  app_vars_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'var1': 'value_global1',
    'var2': 'value_global2'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__global_with_env_override(mocker):
  extra_vars = {}
  global_vars_return_value = {
    'var1': 'value_global1',
    'var2': 'value_global2'
  }
  env_vars_return_value = {
    'var1': 'value_env1'
  }
  app_vars_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'var1': 'value_env1',
    'var2': 'value_global2'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__env_with_app_override(mocker):
  extra_vars = {}
  global_vars_return_value = {
    'var1': 'value_global1',
    'var2': 'value_global2'
  }
  env_vars_return_value = {
    'var1': 'value_env1'
  }
  app_vars_return_value = {
    'var1': 'value_app1'
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'var1': 'value_app1',
    'var2': 'value_global2'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__everything(mocker):
  extra_vars = {
    'var1': 'value_extra1'
  }
  global_vars_return_value = {
    'var2': 'value_global2'
  }
  env_vars_return_value = {
    'var3': 'value_env3'
  }
  app_vars_return_value = {
    'var4': 'value_app4'
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'var1': 'value_extra1',
    'var2': 'value_global2',
    'var3': 'value_env3',
    'var4': 'value_app4'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__resolve_var_simple(mocker):
  extra_vars = {
  }
  global_vars_return_value = {
    'var1': 'value_global1',
    'var2': '${var1}'
  }
  env_vars_return_value = {
  }
  app_vars_return_value = {
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)
  mocker.patch('make_argocd_fly.config.get_cli_params', return_value={'var_identifier': '$'})

  expected_vars = {
    'var1': 'value_global1',
    'var2': 'value_global1'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__resolve_var_env_from_global_simple(mocker):
  extra_vars = {
  }
  global_vars_return_value = {
    'var1': 'value_global1',
  }
  env_vars_return_value = {
    'var2': '${var1}'
  }
  app_vars_return_value = {
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'var1': 'value_global1',
    'var2': 'value_global1'
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__resolve_var_env_from_env(mocker):
  extra_vars = {
  }
  global_vars_return_value = {
    'dict': {
      'subdict': {
        'key1': 'value1'
      },
      'key_global': 'value_global1'
    }
  }
  env_vars_return_value = {
    'dict': {
      'subdict': {
        'key2': 'value2'
      },
      'key_env': '${dict[subdict][key2]}'
    }
  }
  app_vars_return_value = {
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'dict': {
      'subdict': {
        'key1': 'value1',
        'key2': 'value2'
      },
      'key_global': 'value_global1',
      'key_env': 'value2'
    }
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__resolve_var_env_from_global(mocker):
  extra_vars = {
  }
  global_vars_return_value = {
    'dict': {
      'subdict': {
        'key1': 'value1'
      },
      'key_global': 'value_global1'
    }
  }
  env_vars_return_value = {
    'dict': {
      'subdict': {
        'key2': 'value2'
      },
      'key_env': '${dict[subdict][key1]}'
    }
  }
  app_vars_return_value = {
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'dict': {
      'subdict': {
        'key1': 'value1',
        'key2': 'value2'
      },
      'key_global': 'value_global1',
      'key_env': 'value1'
    }
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__resolve_var_global_from_env(mocker):
  extra_vars = {
  }
  global_vars_return_value = {
    'dict': {
      'subdict': {
        'key1': 'value1'
      },
      'key_global': '${dict[subdict][key2]}'
    }
  }
  env_vars_return_value = {
    'dict': {
      'subdict': {
        'key2': 'value2'
      },
      'key_env': 'value_env1'
    }
  }
  app_vars_return_value = {
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'dict': {
      'subdict': {
        'key1': 'value1',
        'key2': 'value2'
      },
      'key_global': 'value2',
      'key_env': 'value_env1'
    }
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

def test_Config__get_vars__resolve_var_global_and_env(mocker):
  extra_vars = {
  }
  global_vars_return_value = {
    'dict': {
      'subdict': {
        'key1': 'value1'
      },
      'key_global': '${dict[subdict][key2]}'
    }
  }
  env_vars_return_value = {
    'dict': {
      'subdict': {
        'key2': 'value2'
      },
      'key_env': '${dict[subdict][key1]}'
    }
  }
  app_vars_return_value = {
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)

  expected_vars = {
    'dict': {
      'subdict': {
        'key1': 'value1',
        'key2': 'value2'
      },
      'key_global': 'value2',
      'key_env': 'value1'
    }
  }
  vars = get_config().get_vars(env_name='test_env', app_name='test_app', extra_vars=extra_vars)
  assert vars == expected_vars

##################
### Config.get_params
##################

def test_Config__get_params__empty_up_to_global(mocker):
  global_params_return_value = {}
  env_params_return_value = {}
  app_params_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_params_return_value)

  params = get_config().get_params()
  assert params.parent_app is None
  assert params.parent_app_env is None
  assert check_lists_equal(params.non_k8s_files_to_render, [])
  assert check_lists_equal(params.exclude_rendering, [])

def test_Config__get_params__empty_up_to_env(mocker):
  global_params_return_value = {}
  env_params_return_value = {}
  app_params_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_params_return_value)

  params = get_config().get_params(env_name='test_env')
  assert params.parent_app is None
  assert params.parent_app_env is None
  assert check_lists_equal(params.non_k8s_files_to_render, [])
  assert check_lists_equal(params.exclude_rendering, [])

def test_Config__get_params__empty_up_to_app(mocker):
  global_params_return_value = {}
  env_params_return_value = {}
  app_params_return_value = {}

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_params_return_value)

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

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_params_return_value)

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

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_params_return_value)

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

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_params_return_value)

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

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_params_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_params_return_value)

  params = get_config().get_params(env_name='test_env', app_name='test_app')
  assert params.parent_app == 'parent_app_value'
  assert params.parent_app_env is None
  assert check_lists_equal(params.non_k8s_files_to_render, ['env_file1', 'env_file2'])
  assert check_lists_equal(params.exclude_rendering, ['app_exclude1', 'app_exclude2'])

import pytest
import textwrap
from make_argocd_fly.config import populate_config, Config, _read_config_file
from make_argocd_fly.exceptions import ConfigFileError, InternalError


##################
### populate_config
##################

def test_populate_config__default_values(tmp_path):
  root_dir = tmp_path
  source_dir = 'source'
  output_dir = 'output'
  tmp_dir = '.tmp'

  config_file_path = tmp_path / 'config.yml'
  config_file_path.write_text('config')

  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert isinstance(config, Config)
  assert config.source_dir == str(source_dir_path)
  assert config.output_dir == str(root_dir / output_dir)
  assert config.tmp_dir == str(root_dir / tmp_dir)

def test_populate_config__non_default_values(tmp_path):
  root_dir = tmp_path
  config_file = 'config_new.yml'
  source_dir = 'source_new'
  output_dir = 'output_new'
  tmp_dir = '.tmp_new'
  config_file_path = tmp_path / config_file
  config_file_path.write_text('config')
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()
  config = populate_config(root_dir=root_dir,
                           config_file=config_file,
                           source_dir=source_dir,
                           output_dir=output_dir,
                           tmp_dir=tmp_dir)

  assert isinstance(config, Config)
  assert config.source_dir == str(source_dir_path)
  assert config.output_dir == str(root_dir / output_dir)
  assert config.tmp_dir == str(root_dir / tmp_dir)

def test_populate_config__missing_source_dir(tmp_path):
  root_dir = tmp_path
  config_file = 'config.yml'

  config_file_path = tmp_path / config_file
  config_file_path.write_text('test')

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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))

  with pytest.raises(ConfigFileError):
    _read_config_file(config_file)

def test__read_config_file__missing_config_file(tmp_path):
  root_dir = tmp_path
  config_file = root_dir / 'config.yml'

  with pytest.raises(InternalError):
    _read_config_file(config_file)

##################
### Config.get_envs
##################

def test_Config__get_envs__valid_config(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
      test_env2: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_envs() == {}

##################
### Config.get_global_vars
##################

def test_Config__get_global_vars__valid_config(tmp_path):
  CONFIG = '''\
    vars:
      test_var: var
      test_var2: var
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
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
  config_file = root_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_app_vars('test_env', 'test_app') == {}

##################
### Config.get_app_params
##################

def test_Config__get_app_params__valid_config(tmp_path):
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
  config_file = root_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  assert config.get_app_params('test_env', 'test_app') == {'param': 'param', 'param2': 'param'}

def test_Config__get_app_params__missing_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_file = root_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_params('test_env2', 'test_app')

def test_Config__get_app_params__undefined_apps(tmp_path):
  CONFIG = '''\
    envs:
      test_env: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_file = root_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_params('test_env', 'test_app')

def test_Config__get_app_params__missing_app(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          test_app: {}
    '''

  root_dir = tmp_path
  source_dir = 'source'
  config_file = root_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir_path = tmp_path / source_dir
  source_dir_path.mkdir()

  config = populate_config(root_dir=root_dir)

  with pytest.raises(ConfigFileError):
    config.get_app_params('test_env', 'test_app2')

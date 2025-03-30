import logging
import pytest
import textwrap
from unittest.mock import MagicMock

from make_argocd_fly.consts import AppParamsNames
from make_argocd_fly.steps import FindAppsStep, RenderYamlStep
from make_argocd_fly.config import populate_config
from make_argocd_fly.utils import check_lists_equal
from make_argocd_fly.exceptions import InternalError

###################
### FindAppsStep
###################

@pytest.fixture
def find_apps_step():
  return FindAppsStep()

def test_FindAppsStep__configure(find_apps_step):
  parent_app_env_name = "my_env"
  parent_app_name = "my_app_deployer"


  find_apps_step.configure(parent_app_env_name, parent_app_name)

  assert find_apps_step.parent_app_name == parent_app_name
  assert find_apps_step.parent_app_env_name == parent_app_env_name

def test_FindAppsStep__get_apps__no_elements(find_apps_step):
  apps = find_apps_step.get_apps()

  assert isinstance(apps, list)
  assert check_lists_equal(apps, [])

@pytest.mark.asyncio
async def test_FindAppsStep__run__without_configure(caplog):
  find_apps_step = FindAppsStep()

  with pytest.raises(InternalError):
    await find_apps_step.run()
  assert 'Step is not configured' in caplog.text

@pytest.mark.asyncio
async def test_FindAppsStep__run__single_app_same_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          bootstrap: {}
          app_1:
            app_deployer: bootstrap
            vars:
              argocd:
                project: my_project
                destination:
                  namespace: my_namespace
    '''

  root_dir = tmp_path
  config_file = tmp_path / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir = tmp_path / 'source'
  source_dir.mkdir()
  populate_config(root_dir, config_file, source_dir)

  parent_app_env_name = "test_env"
  parent_app_name = "bootstrap"
  find_apps_step = FindAppsStep()
  find_apps_step.configure(parent_app_env_name, parent_app_name)

  await find_apps_step.run()
  apps = find_apps_step.get_apps()

  assert check_lists_equal(apps, [('app_1', 'test_env')])

@pytest.mark.asyncio
async def test_FindAppsStep__run__multiple_apps_same_env(tmp_path):
  CONFIG = '''\
  envs:
    test_env:
      apps:
        bootstrap: {}
        app_1:
          app_deployer: bootstrap
          vars:
            argocd:
              project: my_project
              destination:
                namespace: my_namespace
        app_2:
          app_deployer: bootstrap
          vars:
            argocd:
              project: my_project
              destination:
                namespace: my_namespace
  '''

  root_dir = tmp_path
  config_file = tmp_path / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir = tmp_path / 'source'
  source_dir.mkdir()
  populate_config(root_dir, config_file, source_dir)

  parent_app_name = "bootstrap"
  parent_app_env_name = "test_env"
  find_apps_step = FindAppsStep()
  find_apps_step.configure(parent_app_env_name, parent_app_name)

  await find_apps_step.run()
  apps = find_apps_step.get_apps()

  assert check_lists_equal(apps, [('app_1', 'test_env'), ('app_2', 'test_env')])

@pytest.mark.asyncio
async def test_FindAppsStep__run__multiple_apps_different_envs(tmp_path):
  CONFIG = '''\
  envs:
    test_env:
      apps:
        bootstrap: {}
        app_1:
          app_deployer: bootstrap
          vars:
            argocd:
              project: my_project
              destination:
                namespace: my_namespace
    test_env_2:
      apps:
        app_2:
          app_deployer: bootstrap
          app_deployer_env: test_env
          vars:
            argocd:
              project: my_project
              destination:
                namespace: my_namespace
  '''

  root_dir = tmp_path
  config_file = tmp_path / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir = tmp_path / 'source'
  source_dir.mkdir()
  populate_config(root_dir, config_file, source_dir)

  parent_app_name = "bootstrap"
  parent_app_env_name = "test_env"
  find_apps_step = FindAppsStep()
  find_apps_step.configure(parent_app_env_name, parent_app_name)

  await find_apps_step.run()
  apps = find_apps_step.get_apps()

  assert check_lists_equal(apps, [('app_1', 'test_env'), ('app_2', 'test_env_2')])

###################
### RenderYamlStep
###################

@pytest.fixture
def render_yaml_step():
  return RenderYamlStep()

def test_RenderYamlStep__configure(render_yaml_step):
  env_name = "my_env"
  app_name = "my_app"
  mock_yaml_child = MagicMock()
  yml_children = [mock_yaml_child]

  render_yaml_step.configure(env_name, app_name, yml_children )

  assert render_yaml_step.env_name == env_name
  assert render_yaml_step.app_name == app_name
  assert check_lists_equal(render_yaml_step.yml_children, yml_children)

def test_RenderYamlStep__get_resources__no_elements(render_yaml_step):
  resources = render_yaml_step.get_resources()

  assert isinstance(resources, list)
  assert check_lists_equal(resources, [])

###################
### RenderYamlStep._generate_file_path
###################

def test_RenderYamlStep___generate_file_path__step_is_not_configured(render_yaml_step, caplog):
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')
  source_file_path = 'path/file.txt'

  with pytest.raises(InternalError):
    render_yaml_step._generate_file_path(resource_yml, source_file_path)
  assert 'Step is not configured' in caplog.text

def test_RenderYamlStep___generate_file_path__from_yaml_simple(render_yaml_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {}
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')
  source_file_path = 'path/file.txt'

  render_yaml_step.configure(env_name, app_name, yml_children)

  assert render_yaml_step._generate_file_path(resource_yml, source_file_path) == 'my_env/my_app/path/deployment_grafana.yml'
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__non_k8s_files_to_render(render_yaml_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'non_k8s_files_to_render': ['path/file.yml']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  render_yaml_step.configure(env_name, app_name, yml_children)

  assert render_yaml_step._generate_file_path(resource_yml, source_file_path) == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__non_k8s_files_to_render_as_j2(render_yaml_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'non_k8s_files_to_render': ['path/file.yml.j2']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'

  render_yaml_step.configure(env_name, app_name, yml_children)

  assert render_yaml_step._generate_file_path(resource_yml, source_file_path) == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__non_k8s_files_to_render_not_in_the_list(render_yaml_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'non_k8s_files_to_render': ['path/file_1.yml']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  render_yaml_step.configure(env_name, app_name, yml_children)

  with pytest.raises(ValueError):
    render_yaml_step._generate_file_path(resource_yml, source_file_path)
  assert 'Filename cannot be constructed'

  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__non_k8s_files_to_render_as_dir(render_yaml_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'non_k8s_files_to_render': ['path/']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'

  render_yaml_step.configure(env_name, app_name, yml_children)

  assert render_yaml_step._generate_file_path(resource_yml, source_file_path) == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__non_k8s_files_to_render_as_dir_2(render_yaml_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'non_k8s_files_to_render': ['path']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'

  render_yaml_step.configure(env_name, app_name, yml_children)

  assert render_yaml_step._generate_file_path(resource_yml, source_file_path) == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__non_k8s_files_to_render_as_str(render_yaml_step, mocker, caplog):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'non_k8s_files_to_render': 'path/file.yml'
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  render_yaml_step.configure(env_name, app_name, yml_children)

  with pytest.raises(InternalError):
    render_yaml_step._generate_file_path(resource_yml, source_file_path)
  assert 'Application parameter {} must be a list'.format(AppParamsNames.NON_K8S_FILES_TO_RENDER) in caplog.text
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__exclude_rendering(render_yaml_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'exclude_rendering': ['path/file.yml']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  render_yaml_step.configure(env_name, app_name, yml_children)

  with pytest.raises(ValueError):
    render_yaml_step._generate_file_path(resource_yml, source_file_path)
  assert 'Exclude rendering for file {}'.format(source_file_path) in caplog.text
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__exclude_rendering_as_dir(render_yaml_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'exclude_rendering': ['path/']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  render_yaml_step.configure(env_name, app_name, yml_children)

  with pytest.raises(ValueError):
    render_yaml_step._generate_file_path(resource_yml, source_file_path)
  assert 'Exclude rendering for file {}'.format(source_file_path) in caplog.text
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__exclude_rendering_as_dir_2(render_yaml_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'exclude_rendering': ['path']
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  render_yaml_step.configure(env_name, app_name, yml_children)

  with pytest.raises(ValueError):
    render_yaml_step._generate_file_path(resource_yml, source_file_path)
  assert 'Exclude rendering for file {}'.format(source_file_path) in caplog.text
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

def test_RenderYamlStep___generate_file_path__exclude_rendering_as_str(render_yaml_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params.return_value = {
    'exclude_rendering': 'path/'
  }
  mocker.patch('make_argocd_fly.steps.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  render_yaml_step.configure(env_name, app_name, yml_children)

  with pytest.raises(InternalError):
    render_yaml_step._generate_file_path(resource_yml, source_file_path)
  assert 'Application parameter {} must be a list'.format(AppParamsNames.EXCLUDE_RENDERING) in caplog.text
  mock_config.get_app_params.assert_called_once_with(env_name, app_name)

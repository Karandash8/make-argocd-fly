import logging
import pytest
import textwrap
from unittest.mock import MagicMock

from make_argocd_fly.const import AppParamsNames
from make_argocd_fly.step import FindAppsStep, RenderYamlStep, FileNameGeneratorStep
from make_argocd_fly.resource.type import ResourceType
from make_argocd_fly.resource.data import OutputResource
from make_argocd_fly.config import populate_config
from make_argocd_fly.util import check_lists_equal
from make_argocd_fly.exception import InternalError

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
  assert 'FindAppsStep step is not configured' in caplog.text

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
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir = tmp_path / 'source'
  source_dir.mkdir()
  populate_config(root_dir=root_dir, config_dir=config_dir, source_dir=source_dir)

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
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir = tmp_path / 'source'
  source_dir.mkdir()
  populate_config(root_dir=root_dir, config_dir=config_dir, source_dir=source_dir)

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
  config_dir = root_dir / 'config'
  config_dir.mkdir()

  config_file = config_dir / 'config.yml'
  config_file.write_text(textwrap.dedent(CONFIG))
  source_dir = tmp_path / 'source'
  source_dir.mkdir()
  populate_config(root_dir=root_dir, config_dir=config_dir, source_dir=source_dir)

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

def test_RenderYamlStep__get_output_resources__no_elements(render_yaml_step):
  resources = render_yaml_step.get_output_resources()

  assert isinstance(resources, list)
  assert check_lists_equal(resources, [])

###################
### FileNameGeneratorStep
###################

@pytest.fixture
def file_name_generator_step():
  return FileNameGeneratorStep()

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__step_is_not_configured(file_name_generator_step, caplog):
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')
  source_file_path = 'path/file.txt'

  with pytest.raises(InternalError):
    await file_name_generator_step.run()
  assert 'FileNameGeneratorStep step is not configured' in caplog.text

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__from_yaml_simple(file_name_generator_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': []
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
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

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.YAML,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])
  await file_name_generator_step.run()

  assert output_resource.output_resource_path == 'my_env/my_app/path/deployment_grafana.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__non_k8s_files_to_render(file_name_generator_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/file.yml']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.YAML,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])
  await file_name_generator_step.run()

  assert output_resource.output_resource_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__non_k8s_files_to_render_as_j2(file_name_generator_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/file.yml.j2']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])
  await file_name_generator_step.run()

  assert output_resource.output_resource_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__non_k8s_files_to_render_not_in_the_list(file_name_generator_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/file_1.yml']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.YAML,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])
  await file_name_generator_step.run()

  assert 'Filename cannot be constructed' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__non_k8s_files_to_render_as_dir(file_name_generator_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])
  await file_name_generator_step.run()

  assert output_resource.output_resource_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__non_k8s_files_to_render_as_dir_2(file_name_generator_step, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])
  await file_name_generator_step.run()

  assert output_resource.output_resource_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__non_k8s_files_to_render_as_str(file_name_generator_step, mocker, caplog):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': 'path/file.yml'
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])

  with pytest.raises(InternalError):
    await file_name_generator_step.run()
  assert f'Application parameter {AppParamsNames.NON_K8S_FILES_TO_RENDER} must be a list' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__exclude_rendering(file_name_generator_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': ['path/file.yml']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])

  await file_name_generator_step.run()
  assert f'Excluding file {source_file_path}' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__exclude_rendering_as_dir(file_name_generator_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': ['path/']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])

  await file_name_generator_step.run()
  assert f'Excluding file {source_file_path}' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__exclude_rendering_as_dir_2(file_name_generator_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': ['path']
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])

  await file_name_generator_step.run()
  assert f'Excluding file {source_file_path}' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_FileNameGeneratorStep__exclude_rendering_as_str(file_name_generator_step, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': 'path/'
  }
  mocker.patch('make_argocd_fly.step.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  resource_yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'

  output_resource = OutputResource(
      app_name=app_name,
      env_name=env_name,
      resource_type=ResourceType.JINJA2,
      data=resource_yml,
      source_resource_path=source_file_path,
  )

  file_name_generator_step.configure([output_resource])

  with pytest.raises(InternalError):
    await file_name_generator_step.run()
  assert f'Application parameter {AppParamsNames.EXCLUDE_RENDERING} must be a list' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

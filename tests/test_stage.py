import logging
import pytest
import textwrap
from unittest.mock import MagicMock

from make_argocd_fly.const import AppParamsNames
from make_argocd_fly.stage import GenerateManifestNames, DiscoverK8sAppOfAppsApplication
from make_argocd_fly.context import Context, ctx_set, ctx_get
from make_argocd_fly.context.data import Content, Template, OutputResource
from make_argocd_fly.resource.type import ResourceType
from make_argocd_fly.config import populate_config
from make_argocd_fly.util import check_lists_equal
from make_argocd_fly.exception import InternalError

###################
### DiscoverK8sAppOfAppsApplication
###################

@pytest.mark.asyncio
async def test_DiscoverK8sAppOfAppsApplication__run__single_app_same_env(tmp_path):
  CONFIG = '''\
    envs:
      test_env:
        apps:
          bootstrap: {}
          app_1:
            params:
              parent_app: bootstrap
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
  ctx = Context(parent_app_env_name, parent_app_name)
  stage = DiscoverK8sAppOfAppsApplication()

  await stage.run(ctx)
  templates = ctx_get(ctx, stage.provides['template'])
  assert isinstance(templates, list)
  assert len(templates) == 1

  assert check_lists_equal([(template.vars['env_name'], template.vars['app_name']) for template in templates],
                           [('test_env', 'app_1')])

@pytest.mark.asyncio
async def test_DiscoverK8sAppOfAppsApplication__run__multiple_apps_same_env(tmp_path):
  CONFIG = '''\
  envs:
    test_env:
      apps:
        bootstrap: {}
        app_1:
          params:
            parent_app: bootstrap
          vars:
            argocd:
              project: my_project
              destination:
                namespace: my_namespace
        app_2:
          params:
            parent_app: bootstrap
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
  ctx = Context(parent_app_env_name, parent_app_name)
  stage = DiscoverK8sAppOfAppsApplication()

  await stage.run(ctx)
  templates = ctx_get(ctx, stage.provides['template'])
  assert isinstance(templates, list)
  assert len(templates) == 2

  assert check_lists_equal([(template.vars['env_name'], template.vars['app_name']) for template in templates],
                           [('test_env', 'app_1'), ('test_env', 'app_2')])

@pytest.mark.asyncio
async def test_DiscoverK8sAppOfAppsApplication__run__multiple_apps_different_envs(tmp_path):
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
  ctx = Context(parent_app_env_name, parent_app_name)
  stage = DiscoverK8sAppOfAppsApplication()

  await stage.run(ctx)
  templates = ctx_get(ctx, stage.provides['template'])
  assert isinstance(templates, list)
  assert len(templates) == 2

  assert check_lists_equal([(template.vars['env_name'], template.vars['app_name']) for template in templates],
                           [('test_env', 'app_1'), ('test_env_2', 'app_2')])

###################
### GenerateManifestNames
###################

@pytest.fixture
def stage():
  requires = {'content': 'ns1.content'}
  provides = {'files': 'ns2.files'}

  return GenerateManifestNames(requires=requires, provides=provides)

@pytest.mark.asyncio
async def test_GenerateManifestNames__from_yaml_simple(stage, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': []
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')
  source_file_path = 'path/file.txt'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/deployment_grafana.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render(stage, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/file.yml']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_j2(stage, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/file.yml.j2']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_not_in_the_list(stage, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/file_1.yml']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 0
  assert 'Filename cannot be constructed' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_dir(stage, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path/']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)
  env_name = "my_env"
  app_name = "my_app"
  yml_children = [MagicMock()]

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_dir_2(stage, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': ['path']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml.j2'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_str(stage, mocker, caplog):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'non_k8s_files_to_render': 'path/file.yml'
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  with pytest.raises(InternalError):
    await stage.run(ctx)

  assert f'Application parameter {AppParamsNames.NON_K8S_FILES_TO_RENDER} must be a list' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__exclude_rendering(stage, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': ['path/file.yml']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 0
  assert f'Excluding file {source_file_path}' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__exclude_rendering_as_dir(stage, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': ['path/']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 0
  assert f'Excluding file {source_file_path}' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__exclude_rendering_as_dir_2(stage, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': ['path']
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  await stage.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 0
  assert f'Excluding file {source_file_path}' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__exclude_rendering_as_str(stage, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_get_config.return_value = mock_config
  mock_config.get_app_params_deprecated.return_value = {
    'exclude_rendering': 'path/'
  }
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)

  yml = textwrap.dedent('''\
    text: some text
    ''')
  source_file_path = 'path/file.yml'
  env_name = "my_env"
  app_name = "my_app"
  ctx = Context(env_name, app_name)
  output_resource = Content(
      resource_type=ResourceType.YAML,
      data=yml,
      source=source_file_path,
  )

  ctx_set(ctx, 'ns1.content', [output_resource])
  with pytest.raises(InternalError):
    await stage.run(ctx)

  assert f'Application parameter {AppParamsNames.EXCLUDE_RENDERING} must be a list' in caplog.text
  mock_config.get_app_params_deprecated.assert_called_once_with(env_name, app_name)

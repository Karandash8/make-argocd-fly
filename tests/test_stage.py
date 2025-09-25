import logging
import pytest
import textwrap
from unittest.mock import MagicMock, PropertyMock

from make_argocd_fly.param import ParamNames
from make_argocd_fly import default
from make_argocd_fly.stage import GenerateManifestNames, DiscoverK8sAppOfAppsApplication, WriteOnDisk, \
  _resolve_template_vars
from make_argocd_fly.context import Context, ctx_set, ctx_get
from make_argocd_fly.context.data import Content, Template, OutputResource
from make_argocd_fly.resource.viewer import ResourceType
from make_argocd_fly.config import populate_config
from make_argocd_fly.util import check_lists_equal
from make_argocd_fly.exception import InternalError

###################
### _resolve_template_vars
###################

def test__resolve_template_vars__no_vars(mocker):
  output_dir = '/output/dir'
  global_vars_return_value = {}
  env_vars_return_value = {}
  app_vars_return_value = {}
  env_name = 'env1'
  app_name = 'app1'

  expected_vars = {
    'argocd_application_cr_template': default.ARGOCD_APPLICATION_CR_TEMPLATE,
    '__application': {
      'application_name': 'app1-env1',
      'path': 'dir/env1/app1',
    },
    'argocd': default.ARGOCD_DEFAULTS,
    'env_name': env_name,
    'app_name': app_name,
  }

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value=global_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value=env_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value=app_vars_return_value)
  mocker.patch('make_argocd_fly.config.Config.output_dir', new_callable=PropertyMock, return_value=output_dir)

  assert _resolve_template_vars(env_name, app_name) == expected_vars

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
          params:
            parent_app: bootstrap
          vars:
            argocd:
              project: my_project
              destination:
                namespace: my_namespace
    test_env_2:
      apps:
        app_2:
          params:
            parent_app: bootstrap
            parent_app_env: test_env
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
def stage_generate_manifest_names():
  requires = {'content': 'ns1.content'}
  provides = {'files': 'ns2.files'}

  return GenerateManifestNames(requires=requires, provides=provides)

@pytest.mark.asyncio
async def test_GenerateManifestNames__from_yaml_simple(stage_generate_manifest_names, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.non_k8s_files_to_render = []
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
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
  await stage_generate_manifest_names.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/deployment_grafana.yml'
  mock_config.get_params.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render(stage_generate_manifest_names, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.non_k8s_files_to_render =  ['path/file.yml']
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
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
  await stage_generate_manifest_names.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_params.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_j2(stage_generate_manifest_names, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.non_k8s_files_to_render = ['path/file.yml.j2']
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
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
  await stage_generate_manifest_names.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_params.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_not_in_the_list(stage_generate_manifest_names, mocker, caplog):
  caplog.set_level(logging.DEBUG)
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.non_k8s_files_to_render = ['path/file_1.yml']
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
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
  await stage_generate_manifest_names.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 0
  assert 'Filename cannot be constructed' in caplog.text
  mock_config.get_params.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_dir(stage_generate_manifest_names, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.non_k8s_files_to_render = ['path/']
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
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
  await stage_generate_manifest_names.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_params.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_dir_2(stage_generate_manifest_names, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.non_k8s_files_to_render = ['path']
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
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
  await stage_generate_manifest_names.run(ctx)
  output_resources = ctx_get(ctx, 'ns2.files')

  assert isinstance(output_resources, list)
  assert len(output_resources) == 1
  assert isinstance(output_resources[0], OutputResource)
  assert output_resources[0].output_path == 'my_env/my_app/path/file.yml'
  mock_config.get_params.assert_called_once_with(env_name, app_name)

@pytest.mark.asyncio
async def test_GenerateManifestNames__non_k8s_files_to_render_as_str(stage_generate_manifest_names, mocker, caplog):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_params = MagicMock()
  mock_params.non_k8s_files_to_render = 'path/file.yml'
  mock_get_config.return_value = mock_config
  mock_config.get_params.return_value = mock_params
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
    await stage_generate_manifest_names.run(ctx)

  assert f'Application parameter {ParamNames.NON_K8S_FILES_TO_RENDER} must be a list' in caplog.text
  mock_config.get_params.assert_called_once_with(env_name, app_name)

###################
### WriteOnDisk
###################

@pytest.fixture
def stage_write_on_disk():
  requires = {'files': 'ns1.files', 'output_dir': 'ns2.output_dir'}
  return WriteOnDisk(requires=requires)

@pytest.mark.asyncio
async def test_WriteOnDisk___write_no_duplicates(stage_write_on_disk):
  writer = MagicMock()

  await stage_write_on_disk._write(writer, '/output/dir', 'my_env', 'my_app', OutputResource(ResourceType.YAML, 'data', 'source', 'path/file1.txt'))
  await stage_write_on_disk._write(writer, '/output/dir', 'my_env', 'my_app', OutputResource(ResourceType.YAML, 'data', 'source', 'path/file2.txt'))
  await stage_write_on_disk._write(writer, '/output/dir', 'my_env', 'my_app', OutputResource(ResourceType.YAML, 'data', 'source', 'path/file3.txt'))

  assert writer.write.call_count == 3

@pytest.mark.asyncio
async def test_WriteOnDisk___write_with_duplicates(stage_write_on_disk):
  writer = MagicMock()

  await stage_write_on_disk._write(writer, '/output/dir', 'my_env', 'my_app', OutputResource(ResourceType.YAML, 'data', 'source', 'path/file1.txt'))
  await stage_write_on_disk._write(writer, '/output/dir', 'my_env', 'my_app', OutputResource(ResourceType.YAML, 'data', 'source', 'path/file2.txt'))
  with pytest.raises(InternalError):
    await stage_write_on_disk._write(writer, '/output/dir', 'my_env', 'my_app', OutputResource(ResourceType.YAML, 'data', 'source', 'path/file1.txt'))

  assert writer.write.call_count == 2

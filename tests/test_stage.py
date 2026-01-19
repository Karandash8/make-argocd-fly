import asyncio
import pytest
import textwrap
import yaml
from unittest.mock import MagicMock, PropertyMock
from yaml import SafeLoader

from make_argocd_fly import default
from make_argocd_fly.stage import DiscoverK8sAppOfAppsApplication, GenerateNames, _resolve_template_vars
from make_argocd_fly.context import Context, ctx_set, ctx_get
from make_argocd_fly.context.data import Resource
from make_argocd_fly.resource.viewer import ResourceType
from make_argocd_fly.config import populate_config
from make_argocd_fly.util import check_lists_equal
from make_argocd_fly.type import PipelineType, WriterType
from make_argocd_fly.param import Params

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

def _get_params() -> Params:
    return Params()

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
  ctx = Context(parent_app_env_name, parent_app_name, _get_params())
  stage = DiscoverK8sAppOfAppsApplication(
    requires={},
    provides={'templated_resources': 'discovered.templated_resources', 'output_dir': 'discovered.output_dir'},
  )

  await stage.run(ctx)
  templated_resources = ctx_get(ctx, stage.provides['templated_resources'])
  assert isinstance(templated_resources, list)
  assert len(templated_resources) == 1

  assert check_lists_equal([(template.vars['env_name'], template.vars['app_name']) for template in templated_resources],
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
  ctx = Context(parent_app_env_name, parent_app_name, _get_params())
  stage = DiscoverK8sAppOfAppsApplication(
    requires={},
    provides={'templated_resources': 'discovered.templated_resources', 'output_dir': 'discovered.output_dir'},
  )

  await stage.run(ctx)
  templated_resources = ctx_get(ctx, stage.provides['templated_resources'])
  assert isinstance(templated_resources, list)
  assert len(templated_resources) == 2

  assert check_lists_equal([(template.vars['env_name'], template.vars['app_name']) for template in templated_resources],
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
  ctx = Context(parent_app_env_name, parent_app_name, _get_params())
  stage = DiscoverK8sAppOfAppsApplication(
    requires={},
    provides={'templated_resources': 'discovered.templated_resources', 'output_dir': 'discovered.output_dir'},
  )

  await stage.run(ctx)
  templated_resources = ctx_get(ctx, stage.provides['templated_resources'])
  assert isinstance(templated_resources, list)
  assert len(templated_resources) == 2

  assert check_lists_equal([(template.vars['env_name'], template.vars['app_name']) for template in templated_resources],
                           [('test_env', 'app_1'), ('test_env_2', 'app_2')])

###################
### GenerateNames
###################

def _ctx():
  return Context('my_env', 'my_app', _get_params())


def _stage(pipeline_kind: PipelineType):
  requires = {'resources': 'ns1.resources'}
  provides = {'resources': 'ns2.files'}
  return GenerateNames(requires=requires, provides=provides, pipeline_kind=pipeline_kind)


def _patch_get_config(mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_config.get_params.return_value = MagicMock()
  mock_get_config.return_value = mock_config
  mocker.patch('make_argocd_fly.stage.get_config', mock_get_config)
  return mock_config


@pytest.mark.asyncio
async def test_generatenames_k8s_simple_uses_k8s_policy_when_yaml_obj_ok(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  yaml_obj = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'grafana', 'namespace': 'monitoring'}}
  res = Resource(resource_type=ResourceType.YAML,
                 data='...',
                 origin='path/file.yaml',
                 source_path='path/file.yaml',
                 yaml_obj=yaml_obj,
                 writer_type=WriterType.K8S_YAML)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  assert isinstance(out, list) and len(out) == 1
  assert isinstance(out[0], Resource)
  # K8sPolicy default pattern: {rel_dir}/{kind}_{name}.yml
  assert out[0].output_path == 'my_env/my_app/path/deployment_grafana.yml'


@pytest.mark.asyncio
async def test_generatenames_k8s_simple_falls_back_to_source_when_yaml_obj_missing_fields(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  yaml_obj = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {}}
  res = Resource(resource_type=ResourceType.YAML, data='...', origin='cfg/config.yml', source_path='cfg/config.yml', yaml_obj=yaml_obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  assert out == []


@pytest.mark.asyncio
async def test_generatenames_generic_pipeline_always_source_policy_even_for_yaml(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.GENERIC)

  yaml_obj = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'x'}}
  res = Resource(resource_type=ResourceType.YAML, data='...', origin='secrets/db.yml.j2', source_path='secrets/db.yml.j2', yaml_obj=yaml_obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  # SourcePolicy strips .j2 but keeps real extension
  assert out[0].output_path == 'my_env/my_app/secrets/db.yml'


@pytest.mark.asyncio
async def test_generatenames_kustomize_routes_driver_files_to_source_policy(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_KUSTOMIZE)

  # kustomization and values, hence source policy
  kustomization = Resource(resource_type=ResourceType.YAML, data='...', origin='kustomization.yaml', source_path='kustomization.yaml')
  values = Resource(resource_type=ResourceType.YAML, data='...', origin='values.yml', source_path='values.yml')

  # a regular rendered manifest with yaml_obj, hence k8s policy
  obj = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'api'}}
  manifest = Resource(resource_type=ResourceType.YAML,
                      data='...',
                      origin='manifests/out.yaml',
                      source_path='manifests/out.yaml',
                      yaml_obj=obj,
                      writer_type=WriterType.K8S_YAML)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [kustomization, values, manifest])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  # order is sorted by source name inside stage, so check membership
  paths = {r.output_path for r in out}
  assert 'my_env/my_app/kustomization.yaml' in paths
  assert 'my_env/my_app/values.yml' in paths
  assert 'my_env/my_app/manifests/deployment_api.yml' in paths


@pytest.mark.asyncio
async def test_generatenames_helmfile_routes_driver_file_to_source_policy(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_HELMFILE)

  helmfile = Resource(resource_type=ResourceType.YAML, data='...', origin='helmfile.yaml', source_path='helmfile.yaml')
  obj = {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'web'}}
  svc = Resource(resource_type=ResourceType.YAML,
                 data='...',
                 origin='templates/svc.yaml',
                 source_path='templates/svc.yaml',
                 yaml_obj=obj,
                 writer_type=WriterType.K8S_YAML)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [helmfile, svc])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  paths = {r.output_path for r in out}
  assert 'my_env/my_app/helmfile.yaml' in paths
  assert 'my_env/my_app/templates/service_web.yml' in paths


@pytest.mark.asyncio
async def test_generatenames_dedupes_conflicts_with_suffix(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  # Two manifests that resolve to the same filename, hence second gets _1
  obj1 = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'api'}}
  obj2 = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'api'}}

  a = Resource(resource_type=ResourceType.YAML,
               data='...',
               origin='src/a.yaml',
               source_path='src/a.yaml',
               yaml_obj=obj1,
               writer_type=WriterType.K8S_YAML)
  b = Resource(resource_type=ResourceType.YAML,
               data='...',
               origin='src/b.yaml',
               source_path='src/b.yaml',
               yaml_obj=obj2,
               writer_type=WriterType.K8S_YAML)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [a, b])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  # Sorted by source , hence 'a.yaml' first
  assert out[0].output_path == 'my_env/my_app/src/deployment_api.yml'
  assert out[1].output_path == 'my_env/my_app/src/deployment_api_1.yml'

@pytest.mark.asyncio
async def test_generatenames_k8s_simple_uses_k8s_policy_when_yaml_has_special_characters(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  yaml_str = '''\
    apiVersion: v1
    kind: Pod
    metadata:
      name: "airbyte-test-connection"
  '''
  yaml_obj = yaml.load(yaml_str, Loader=SafeLoader)
  res = Resource(resource_type=ResourceType.YAML,
                 data='...',
                 origin='path/file.yaml',
                 source_path='path/file.yaml',
                 yaml_obj=yaml_obj,
                 writer_type=WriterType.K8S_YAML)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  assert isinstance(out, list) and len(out) == 1
  assert isinstance(out[0], Resource)
  assert out[0].output_path == 'my_env/my_app/path/pod_airbyte-test-connection.yml'

@pytest.mark.asyncio
async def test_generatenames_k8s_simple_skips_non_yaml(mocker, caplog):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  text = Resource(resource_type=ResourceType.UNKNOWN, data='hello', origin='docs/readme.txt', source_path='docs/readme.txt', yaml_obj=None)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [text])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  assert out == []  # non-YAML skipped in K8s pipelines
  assert f'Skipping resource due to no naming policy found (origin={text.origin} path={text.source_path}) for application {ctx.app_name} in environment {ctx.env_name}' in caplog.text

@pytest.mark.asyncio
async def test_generatenames_k8s_simple_skips_when_yaml_obj_missing(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  # YAML file but parser failed earlier -> yaml_obj is None -> strict skip
  y = Resource(resource_type=ResourceType.YAML, data=': : :', origin='cfg/bad.yaml', source_path='cfg/bad.yaml', yaml_obj=None)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [y])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  assert out == []  # no fallback for k8s policy

@pytest.mark.asyncio
async def test_generatenames_kustomize_uses_dynamic_config_list_for_source_policy(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_KUSTOMIZE)

  # Pretend this arbitrary path is flagged as a kustomize config file
  driver = Resource(resource_type=ResourceType.YAML, data='...', origin='custom/path/my-kustomize-driver.yml', source_path='custom/path/my-kustomize-driver.yml')
  obj = Resource(resource_type=ResourceType.YAML,
                 data='...',
                 origin='manifests/app.yaml',
                 source_path='manifests/app.yaml',
                 yaml_obj={'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'api'}},
                 writer_type=WriterType.K8S_YAML)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [driver, obj])
  # Dynamic routing lists
  ctx_set(ctx, 'discovered.kustomize_config_files', {'custom/path/my-kustomize-driver.yml'})
  ctx_set(ctx, 'discovered.helmfile_config_files', set())

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  paths = {r.output_path for r in out}
  assert 'my_env/my_app/custom/path/my-kustomize-driver.yml' in paths  # source policy
  assert 'my_env/my_app/manifests/deployment_api.yml' in paths         # k8s policy

@pytest.mark.asyncio
async def test_generatenames_helmfile_uses_dynamic_config_list_for_source_policy(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_HELMFILE)

  driver = Resource(resource_type=ResourceType.YAML, data='...', origin='charts/root/helmfile-prod.yaml', source_path='charts/root/helmfile-prod.yaml')
  obj = Resource(resource_type=ResourceType.YAML,
                 data='...',
                 origin='rendered/svc.yaml',
                 source_path='rendered/svc.yaml',
                 yaml_obj={'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'web'}},
                 writer_type=WriterType.K8S_YAML)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [driver, obj])
  ctx_set(ctx, 'discovered.kustomize_config_files', set())
  ctx_set(ctx, 'discovered.helmfile_config_files', {'charts/root/helmfile-prod.yaml'})

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  paths = {r.output_path for r in out}
  assert 'my_env/my_app/charts/root/helmfile-prod.yaml' in paths       # source policy via dynamic list
  assert 'my_env/my_app/rendered/service_web.yml' in paths             # k8s policy

@pytest.mark.asyncio
async def test_generatenames_generic_includes_non_yaml_and_strips_j2(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.GENERIC)

  txt = Resource(resource_type=ResourceType.UNKNOWN, data='hello', origin='docs/intro.txt', source_path='docs/intro.txt')
  templ = Resource(resource_type=ResourceType.YAML, data='...', origin='secrets/values.yml.j2', source_path='secrets/values.yml.j2')  # SourcePolicy strips .j2

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [txt, templ])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  paths = {r.output_path for r in out}
  assert 'my_env/my_app/docs/intro.txt' in paths
  assert 'my_env/my_app/secrets/values.yml' in paths

@pytest.mark.asyncio
async def test_generatenames_k8s_app_of_apps_behaves_like_k8s_simple(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_APP_OF_APPS)

  good = Resource(resource_type=ResourceType.YAML,
                 data='...',
                 origin='a/cm.yaml',
                 source_path='a/cm.yaml',
                 yaml_obj={'apiVersion': 'v1', 'kind': 'Application', 'metadata': {'name': 'app'}},
                 writer_type=WriterType.K8S_YAML)
  bad = Resource(resource_type=ResourceType.YAML, data='...', origin='b/cm.yaml', source_path='b/cm.yaml', yaml_obj=None)  # will be skipped

  ctx = _ctx()
  ctx_set(ctx, 'ns1.resources', [bad, good])  # ordering verifies deterministic sort + dedupe path

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  assert len(out) == 1
  assert isinstance(out[0], Resource)
  assert out[0].output_path == 'my_env/my_app/a/application_app.yml'

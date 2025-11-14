import asyncio
import pytest
import textwrap
import yaml
from unittest.mock import MagicMock, PropertyMock
from yaml import SafeLoader

from make_argocd_fly import default
from make_argocd_fly.stage import (DiscoverK8sAppOfAppsApplication, WriteOnDisk, GenerateNames, _resolve_template_vars,
                                   _scan_viewer)
from make_argocd_fly.context import Context, ctx_set, ctx_get
from make_argocd_fly.context.data import Content, Template, OutputResource
from make_argocd_fly.resource.viewer import ResourceType, build_scoped_viewer
from make_argocd_fly.config import populate_config
from make_argocd_fly.util import check_lists_equal
from make_argocd_fly.exception import InternalError
from make_argocd_fly.limits import RuntimeLimits
from make_argocd_fly.type import PipelineType

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
### _scan_viewer
###################

def _paths(children):
  # Helper to extract rel paths in a deterministic order
  return sorted([c.rel_path for c in children])

def _write(p, text=''):
  p.parent.mkdir(parents=True, exist_ok=True)
  p.write_text(text)

def test_scan_viewer__no_excludes_yaml_non_template(tmp_path):
  root = tmp_path / 'src'
  # files
  _write(root / 'a' / 'config.yml', 'k: v')
  _write(root / 'a' / 'config.yml.j2', 'k: {{ v }}')  # template, should be excluded when template=False
  _write(root / 'a' / 'notes.txt', 'n/a')             # non-yaml
  _write(root / 'b' / 'sub' / 'keep.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = _scan_viewer(
    viewer=viewer,
    resource_types=[ResourceType.YAML],
    template=False,
    search_subdirs=None,
    excludes=None,
  )

  assert _paths(children) == [
    'a/config.yml',
    'b/sub/keep.yml',
    'b/sub/secret.yml',
  ]

def test_scan_viewer__exclude_by_prefix(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'config.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'keep.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = _scan_viewer(
    viewer=viewer,
    resource_types=[ResourceType.YAML],
    template=False,
    excludes=['b/sub'],          # prefix exclude
  )

  assert _paths(children) == ['a/config.yml']

def test_scan_viewer__exclude_by_glob(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'b' / 'sub' / 'keep.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret.yml', 'k: v')
  _write(root / 'b' / 'sub' / 'secret-values.yaml', 'k: v')
  _write(root / 'b' / 'other' / 'secret.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = _scan_viewer(
    viewer=viewer,
    resource_types=[ResourceType.YAML],
    template=False,
    excludes=['b/**/secret*'],   # glob exclude across nested dirs
  )

  assert _paths(children) == ['b/sub/keep.yml']

def test_scan_viewer__template_true_picks_j2_yaml(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'plain.yml', 'k: v')
  _write(root / 'a' / 'tpl.yml.j2', 'k: {{ v }}')
  _write(root / 'a' / 'tpl.txt.j2', 'plain')  # non-yaml template -> not YAML ResourceType

  viewer = build_scoped_viewer(str(root))

  # Non-templates
  non_tpl = _scan_viewer(
    viewer=viewer,
    resource_types=[ResourceType.YAML],
    template=False,
  )
  assert _paths(non_tpl) == ['a/plain.yml']

  # Templates
  tpl = _scan_viewer(
    viewer=viewer,
    resource_types=[ResourceType.YAML],
    template=True,
  )
  # Only YAML templates (e.g., *.yml.j2 / *.yaml.j2) should be included
  assert _paths(tpl) == ['a/tpl.yml.j2']

def test_scan_viewer__search_subdirs_limits_scope(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'a' / 'one.yml', 'k: v')
  _write(root / 'b' / 'two.yml', 'k: v')
  _write(root / 'b' / 'nested' / 'three.yml', 'k: v')

  viewer = build_scoped_viewer(str(root))

  children = _scan_viewer(
    viewer=viewer,
    resource_types=[ResourceType.YAML],
    template=False,
    search_subdirs=['a'],
  )
  assert _paths(children) == ['a/one.yml']

def test_scan_viewer__combined_template_and_excludes(tmp_path):
  root = tmp_path / 'src'
  _write(root / 'env' / 'values.yml.j2', 'k: {{ v }}')
  _write(root / 'env' / 'patch.yml.j2', 'k: {{ v }}')
  _write(root / 'env' / 'readme.txt', 'ignore')

  viewer = build_scoped_viewer(str(root))

  tpl = _scan_viewer(
    viewer=viewer,
    resource_types=[ResourceType.YAML],
    template=True,
    excludes=['env/patch*'],   # should exclude the template by glob
  )
  assert _paths(tpl) == ['env/values.yml.j2']

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
  stage = DiscoverK8sAppOfAppsApplication(
    requires={},
    provides={'template': 'discover.template', 'output_dir': 'discover.output_dir'},
  )

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
  stage = DiscoverK8sAppOfAppsApplication(
    requires={},
    provides={'template': 'discover.template', 'output_dir': 'discover.output_dir'},
  )

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
  stage = DiscoverK8sAppOfAppsApplication(
    requires={},
    provides={'template': 'discover.template', 'output_dir': 'discover.output_dir'},
  )

  await stage.run(ctx)
  templates = ctx_get(ctx, stage.provides['template'])
  assert isinstance(templates, list)
  assert len(templates) == 2

  assert check_lists_equal([(template.vars['env_name'], template.vars['app_name']) for template in templates],
                           [('test_env', 'app_1'), ('test_env_2', 'app_2')])

###################
### GenerateNames
###################

def _ctx():
  return Context('my_env', 'my_app')


def _stage(pipeline_kind: PipelineType):
  requires = {'content': 'ns1.content'}
  provides = {'files': 'ns2.files'}
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
  res = Content(resource_type=ResourceType.YAML, data='...', source='path/file.yaml', yaml_obj=yaml_obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  assert isinstance(out, list) and len(out) == 1
  assert isinstance(out[0], OutputResource)
  # K8sPolicy default pattern: {rel_dir}/{kind}_{name}.yml
  assert out[0].output_path == 'my_env/my_app/path/deployment_grafana.yml'


@pytest.mark.asyncio
async def test_generatenames_k8s_simple_falls_back_to_source_when_yaml_obj_missing_fields(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  yaml_obj = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {}}
  res = Content(resource_type=ResourceType.YAML, data='...', source='cfg/config.yml', yaml_obj=yaml_obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  assert out == []


@pytest.mark.asyncio
async def test_generatenames_generic_pipeline_always_source_policy_even_for_yaml(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.GENERIC)

  yaml_obj = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'x'}}
  res = Content(resource_type=ResourceType.YAML, data='...', source='secrets/db.yml.j2', yaml_obj=yaml_obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  # SourcePolicy strips .j2 but keeps real extension
  assert out[0].output_path == 'my_env/my_app/secrets/db.yml'


@pytest.mark.asyncio
async def test_generatenames_kustomize_routes_driver_files_to_source_policy(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_KUSTOMIZE)

  # kustomization and values, hence source policy
  kustomization = Content(ResourceType.YAML, '...', 'kustomization.yaml')
  values = Content(ResourceType.YAML, '...', 'values.yml')

  # a regular rendered manifest with yaml_obj, hence k8s policy
  obj = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'api'}}
  manifest = Content(ResourceType.YAML, '...', 'manifests/out.yaml', yaml_obj=obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [kustomization, values, manifest])

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

  helmfile = Content(ResourceType.YAML, '...', 'helmfile.yaml')
  obj = {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'web'}}
  svc = Content(ResourceType.YAML, '...', 'templates/svc.yaml', yaml_obj=obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [helmfile, svc])

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

  a = Content(ResourceType.YAML, '...', 'src/a.yaml', yaml_obj=obj1)
  b = Content(ResourceType.YAML, '...', 'src/b.yaml', yaml_obj=obj2)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [a, b])

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
  res = Content(resource_type=ResourceType.YAML, data='...', source='path/file.yaml', yaml_obj=yaml_obj)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [res])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')

  assert isinstance(out, list) and len(out) == 1
  assert isinstance(out[0], OutputResource)
  assert out[0].output_path == 'my_env/my_app/path/pod_airbyte-test-connection.yml'

@pytest.mark.asyncio
async def test_generatenames_k8s_simple_skips_non_yaml(mocker, caplog):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  text = Content(resource_type=ResourceType.UNKNOWN, data='hello', source='docs/readme.txt', yaml_obj=None)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [text])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  assert out == []  # non-YAML skipped in K8s pipelines
  assert "Skipping resource due to unknown policy 'None'" in caplog.text

@pytest.mark.asyncio
async def test_generatenames_k8s_simple_skips_when_yaml_obj_missing(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_SIMPLE)

  # YAML file but parser failed earlier -> yaml_obj is None -> strict skip
  y = Content(resource_type=ResourceType.YAML, data=': : :', source='cfg/bad.yaml', yaml_obj=None)

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [y])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  assert out == []  # no fallback for k8s policy

@pytest.mark.asyncio
async def test_generatenames_kustomize_uses_dynamic_config_list_for_source_policy(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_KUSTOMIZE)

  # Pretend this arbitrary path is flagged as a kustomize config file
  driver = Content(ResourceType.YAML, '...', 'custom/path/my-kustomize-driver.yml')
  obj = Content(ResourceType.YAML, '...', 'manifests/app.yaml',
                yaml_obj={'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'api'}})

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [driver, obj])
  # Dynamic routing lists
  ctx_set(ctx, 'discover.kustomize.config_files', {'custom/path/my-kustomize-driver.yml'})
  ctx_set(ctx, 'discover.helmfile.config_files', set())

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  paths = {r.output_path for r in out}
  assert 'my_env/my_app/custom/path/my-kustomize-driver.yml' in paths  # source policy
  assert 'my_env/my_app/manifests/deployment_api.yml' in paths         # k8s policy

@pytest.mark.asyncio
async def test_generatenames_helmfile_uses_dynamic_config_list_for_source_policy(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_HELMFILE)

  driver = Content(ResourceType.YAML, '...', 'charts/root/helmfile-prod.yaml')
  obj = Content(ResourceType.YAML, '...', 'rendered/svc.yaml',
                yaml_obj={'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'web'}})

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [driver, obj])
  ctx_set(ctx, 'discover.kustomize.config_files', set())
  ctx_set(ctx, 'discover.helmfile.config_files', {'charts/root/helmfile-prod.yaml'})

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  paths = {r.output_path for r in out}
  assert 'my_env/my_app/charts/root/helmfile-prod.yaml' in paths       # source policy via dynamic list
  assert 'my_env/my_app/rendered/service_web.yml' in paths             # k8s policy

@pytest.mark.asyncio
async def test_generatenames_generic_includes_non_yaml_and_strips_j2(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.GENERIC)

  txt = Content(ResourceType.UNKNOWN, 'hello', 'docs/intro.txt')
  templ = Content(ResourceType.YAML, '...', 'secrets/values.yml.j2')  # SourcePolicy strips .j2

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [txt, templ])

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  paths = {r.output_path for r in out}
  assert 'my_env/my_app/docs/intro.txt' in paths
  assert 'my_env/my_app/secrets/values.yml' in paths

@pytest.mark.asyncio
async def test_generatenames_k8s_app_of_apps_behaves_like_k8s_simple(mocker):
  _patch_get_config(mocker)
  stage = _stage(PipelineType.K8S_APP_OF_APPS)

  good = Content(ResourceType.YAML, '...', 'a/cm.yaml',
                 yaml_obj={'apiVersion': 'v1', 'kind': 'Application', 'metadata': {'name': 'app'}})
  bad = Content(ResourceType.YAML, '...', 'b/cm.yaml', yaml_obj=None)  # will be skipped

  ctx = _ctx()
  ctx_set(ctx, 'ns1.content', [bad, good])  # ordering verifies deterministic sort + dedupe path

  await stage.run(ctx)
  out = ctx_get(ctx, 'ns2.files')
  assert len(out) == 1
  assert isinstance(out[0], OutputResource)
  assert out[0].output_path == 'my_env/my_app/a/application_app.yml'

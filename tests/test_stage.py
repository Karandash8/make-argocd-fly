import asyncio
import pytest
import textwrap
import yaml
import os
from unittest.mock import MagicMock, PropertyMock
from yaml import SafeLoader

from make_argocd_fly import default
from make_argocd_fly.stage import (DiscoverK8sAppOfAppsApplication, GenerateNames, _resolve_template_vars,
                                   DiscoverK8sKustomizeApplication, DiscoverK8sSimpleApplication, DiscoverGenericApplication,
                                   DiscoverK8sHelmfileApplication)
from make_argocd_fly.stage.discover import _find_child_apps
from make_argocd_fly.context import Context, ctx_set, ctx_get
from make_argocd_fly.context.data import Resource
from make_argocd_fly.resource.viewer import ResourceType, build_scoped_viewer
from make_argocd_fly.config import populate_config
from make_argocd_fly.util import check_lists_equal
from make_argocd_fly.type import PipelineType, WriterType
from make_argocd_fly.param import Params
from make_argocd_fly.stage.discover import _resolve_kustomize_search_subdirs, _resolve_kustomize_exec_dir
from make_argocd_fly.exception import InternalError
from unittest.mock import patch


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
  mocker.patch('make_argocd_fly.config.Config.final_output_dir', new_callable=PropertyMock, return_value=output_dir)
  mocker.patch('make_argocd_fly.config.Config.get_params', return_value=Params())

  assert _resolve_template_vars(env_name, app_name) == expected_vars

def test__resolve_template_vars__short_format_nested_app(mocker):
  # short format: only the last path segment is used — the source of the collision bug
  output_dir = '/output/dir'
  env_name = 'env1'
  app_name = 'subdir/app'

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config.final_output_dir', new_callable=PropertyMock, return_value=output_dir)
  mocker.patch('make_argocd_fly.config.Config.get_params', return_value=Params())

  result = _resolve_template_vars(env_name, app_name)
  assert result['__application']['application_name'] == 'app-env1'


def test__resolve_template_vars__short_format_collision(mocker):
  # demonstrates that short format produces the same application_name for
  # 'subdir/app' and 'subdir_2/app', which is the collision this feature solves
  output_dir = '/output/dir'
  env_name = 'env1'

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config.final_output_dir', new_callable=PropertyMock, return_value=output_dir)
  mocker.patch('make_argocd_fly.config.Config.get_params', return_value=Params())

  result_1 = _resolve_template_vars(env_name, 'subdir/app')
  result_2 = _resolve_template_vars(env_name, 'subdir_2/app')
  assert result_1['__application']['application_name'] == result_2['__application']['application_name']


def test__resolve_template_vars__full_format_nested_app(mocker):
  # full format: entire path is used, slashes become dashes
  output_dir = '/output/dir'
  env_name = 'env1'
  app_name = 'subdir/app'

  params = Params()
  params.populate_params(application_name='full')

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config.final_output_dir', new_callable=PropertyMock, return_value=output_dir)
  mocker.patch('make_argocd_fly.config.Config.get_params', return_value=params)

  result = _resolve_template_vars(env_name, app_name)
  assert result['__application']['application_name'] == 'subdir-app-env1'


def test__resolve_template_vars__full_format_no_collision(mocker):
  # full format: 'subdir/app' and 'subdir_2/app' now produce distinct names
  output_dir = '/output/dir'
  env_name = 'env1'

  params = Params()
  params.populate_params(application_name='full')

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config.final_output_dir', new_callable=PropertyMock, return_value=output_dir)
  mocker.patch('make_argocd_fly.config.Config.get_params', return_value=params)

  result_1 = _resolve_template_vars(env_name, 'subdir/app')
  result_2 = _resolve_template_vars(env_name, 'subdir_2/app')
  assert result_1['__application']['application_name'] != result_2['__application']['application_name']
  assert result_1['__application']['application_name'] == 'subdir-app-env1'
  assert result_2['__application']['application_name'] == 'subdir-2-app-env1'


def test__resolve_template_vars__full_format_underscores_replaced(mocker):
  # underscores in any part of the path are replaced with dashes
  output_dir = '/output/dir'
  env_name = 'my_env'
  app_name = 'my_group/my_app'

  params = Params()
  params.populate_params(application_name='full')

  mocker.patch('make_argocd_fly.config.Config._get_global_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_env_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config._get_app_scope', return_value={})
  mocker.patch('make_argocd_fly.config.Config.final_output_dir', new_callable=PropertyMock, return_value=output_dir)
  mocker.patch('make_argocd_fly.config.Config.get_params', return_value=params)

  result = _resolve_template_vars(env_name, app_name)
  assert result['__application']['application_name'] == 'my-group-my-app-my-env'

###################
### DiscoverK8sSimpleApplication.run()
###################

def _patch_config(mocker, tmp_dir: str = '/tmp/kustomize', output_dir: str = '/output'):
  mock_config = MagicMock()
  mock_config.runtime_output_dir = output_dir
  mock_config.tmp_dir = tmp_dir
  mocker.patch('make_argocd_fly.stage.discover.get_config', return_value=mock_config)
  return mock_config


def _patch_template_vars(mocker, return_value: dict | None = None):
  if return_value is None:
    return_value = {'argocd_application_cr_template': ''}
  mocker.patch('make_argocd_fly.stage.discover._resolve_template_vars', return_value=return_value)


def _make_simple_stage():
  return DiscoverK8sSimpleApplication(
    requires={'viewer': 'source.viewer'},
    provides={
      'resources': 'discovered.resources',
      'templated_resources': 'discovered.templated_resources',
      'output_dir': 'discovered.output_dir',
    }
  )


def _make_simple_ctx(env_name: str, app_name: str, params: Params | None = None) -> Context:
  if params is None:
    params = Params()
  return Context(env_name, app_name, params)


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__plain_yaml_discovered_as_resource(tmp_path, mocker):
  (tmp_path / 'deployment.yaml').write_text('kind: Deployment')
  (tmp_path / 'service.yml').write_text('kind: Service')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'deployment.yaml' in origins
  assert 'service.yml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__j2_files_discovered_as_templated_resources(tmp_path, mocker):
  (tmp_path / 'deployment.yaml').write_text('kind: Deployment')
  (tmp_path / 'configmap.yaml.j2').write_text('kind: ConfigMap\ndata:\n  key: {{ value }}')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  templated = ctx_get(ctx, stage.provides['templated_resources'])

  resource_origins = {r.origin for r in resources}
  templated_origins = {r.origin for r in templated}

  # plain YAML only in resources, template only in templated_resources
  assert 'deployment.yaml' in resource_origins
  assert 'configmap.yaml.j2' not in resource_origins
  assert 'configmap.yaml.j2' in templated_origins
  assert 'deployment.yaml' not in templated_origins


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__non_yaml_files_not_discovered(tmp_path, mocker):
  (tmp_path / 'deployment.yaml').write_text('kind: Deployment')
  (tmp_path / 'readme.txt').write_text('some text')
  (tmp_path / 'script.sh').write_text('#!/bin/bash')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'readme.txt' not in origins
  assert 'script.sh' not in origins
  assert 'deployment.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__subdirectory_files_discovered(tmp_path, mocker):
  subdir = tmp_path / 'manifests'
  subdir.mkdir()
  (subdir / 'deployment.yaml').write_text('kind: Deployment')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'manifests/deployment.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__exclude_rendering_filters_resources(tmp_path, mocker):
  (tmp_path / 'deployment.yaml').write_text('kind: Deployment')
  (tmp_path / 'secret.yaml').write_text('kind: Secret')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  params = Params()
  params.populate_params(exclude_rendering=['secret.yaml'])
  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app', params)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'secret.yaml' not in origins
  assert 'deployment.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__exclude_rendering_also_filters_templated(tmp_path, mocker):
  (tmp_path / 'deployment.yaml.j2').write_text('kind: Deployment\nname: {{ name }}')
  (tmp_path / 'secret.yaml.j2').write_text('kind: Secret\nname: {{ name }}')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  params = Params()
  params.populate_params(exclude_rendering=['secret.yaml.j2'])
  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app', params)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  templated = ctx_get(ctx, stage.provides['templated_resources'])
  origins = {r.origin for r in templated}
  assert 'secret.yaml.j2' not in origins
  assert 'deployment.yaml.j2' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__empty_directory_produces_no_resources(tmp_path, mocker):
  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['resources']) == []
  assert ctx_get(ctx, stage.provides['templated_resources']) == []


@pytest.mark.asyncio
async def test_DiscoverK8sSimpleApplication__run__output_dir_set_from_config(tmp_path, mocker):
  _patch_config(mocker, output_dir='/my/output/dir')
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_simple_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['output_dir']) == '/my/output/dir'

###################
### _resolve_kustomize_search_subdirs
### _resolve_kustomize_exec_dir
###################

# --- _resolve_kustomize_search_subdirs ---

def test_resolve_kustomize_search_subdirs__base_and_env(tmp_path):
  (tmp_path / 'base').mkdir()
  (tmp_path / 'dev').mkdir()
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', [], 'my_app')
  assert set(result) == {'base', 'dev'}


def test_resolve_kustomize_search_subdirs__only_base(tmp_path):
  (tmp_path / 'base').mkdir()
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', [], 'my_app')
  assert result == ['base']


def test_resolve_kustomize_search_subdirs__only_env(tmp_path):
  (tmp_path / 'dev').mkdir()
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', [], 'my_app')
  assert result == ['dev']


def test_resolve_kustomize_search_subdirs__no_base_no_env_returns_none(tmp_path):
  # no base or env dir — should fall through to None (search everything)
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', [], 'my_app')
  assert result is None


def test_resolve_kustomize_search_subdirs__common_dir_included(tmp_path):
  (tmp_path / 'base').mkdir()
  (tmp_path / 'dev').mkdir()
  (tmp_path / 'common').mkdir()
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', ['common'], 'my_app')
  assert set(result) == {'base', 'dev', 'common'}


def test_resolve_kustomize_search_subdirs__missing_common_dir_skipped(tmp_path, caplog):
  (tmp_path / 'base').mkdir()
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', ['nonexistent'], 'my_app')
  # nonexistent dir is skipped — only base survives
  assert result == ['base']
  assert 'nonexistent' in caplog.text


def test_resolve_kustomize_search_subdirs__common_dir_only_added_when_base_or_env_exist(tmp_path):
  # kustomize_common_dirs are only appended when candidate_subdirs is non-empty
  (tmp_path / 'common').mkdir()
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', ['common'], 'my_app')
  assert result is None


def test_resolve_kustomize_search_subdirs__multiple_common_dirs(tmp_path):
  (tmp_path / 'base').mkdir()
  (tmp_path / 'common').mkdir()
  (tmp_path / 'patches').mkdir()
  viewer = build_scoped_viewer(tmp_path)

  result = _resolve_kustomize_search_subdirs(viewer, 'dev', ['common', 'patches'], 'my_app')
  assert set(result) == {'base', 'common', 'patches'}


# --- _resolve_kustomize_exec_dir ---

def test_resolve_kustomize_exec_dir__env_dir_takes_priority(tmp_path):
  env_dir = tmp_path / 'dev'
  env_dir.mkdir()
  (env_dir / 'kustomization.yaml').write_text('resources: []')
  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'kustomization.yaml').write_text('resources: []')
  viewer = build_scoped_viewer(tmp_path)

  assert _resolve_kustomize_exec_dir(viewer, 'dev', 'my_app') == 'dev'


def test_resolve_kustomize_exec_dir__base_when_no_env_dir(tmp_path):
  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'kustomization.yaml').write_text('resources: []')
  viewer = build_scoped_viewer(tmp_path)

  assert _resolve_kustomize_exec_dir(viewer, 'dev', 'my_app') == 'base'


def test_resolve_kustomize_exec_dir__root_when_no_env_or_base(tmp_path):
  (tmp_path / 'kustomization.yaml').write_text('resources: []')
  viewer = build_scoped_viewer(tmp_path)

  assert _resolve_kustomize_exec_dir(viewer, 'dev', 'my_app') == '.'


def test_resolve_kustomize_exec_dir__raises_when_no_kustomization_found(tmp_path):
  viewer = build_scoped_viewer(tmp_path)

  with pytest.raises(InternalError):
    _resolve_kustomize_exec_dir(viewer, 'dev', 'my_app')


def test_resolve_kustomize_exec_dir__yml_extension_also_detected(tmp_path):
  env_dir = tmp_path / 'prod'
  env_dir.mkdir()
  (env_dir / 'kustomization.yml').write_text('resources: []')
  viewer = build_scoped_viewer(tmp_path)

  assert _resolve_kustomize_exec_dir(viewer, 'prod', 'my_app') == 'prod'


def test_resolve_kustomize_exec_dir__capitalised_filename_also_detected(tmp_path):
  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'Kustomization.yaml').write_text('resources: []')
  viewer = build_scoped_viewer(tmp_path)

  assert _resolve_kustomize_exec_dir(viewer, 'dev', 'my_app') == 'base'

###################
### DiscoverK8sKustomizeApplication.run()
###################

def _make_kustomize_stage():
  return DiscoverK8sKustomizeApplication(
    requires={'viewer': 'source.viewer'},
    provides={
      'resources': 'discovered.resources',
      'templated_resources': 'discovered.templated_resources',
      'extra_resources': 'discovered.extra_resources',
      'templated_extra_resources': 'discovered.templated_extra_resources',
      'kustomize_exec_dir': 'discovered.kustomize_exec_dir',
      'tmp_dir': 'discovered.tmp_dir',
      'output_dir': 'discovered.output_dir',
    }
  )


def _make_kustomize_ctx(env_name: str, app_name: str, params: Params | None = None) -> Context:
  if params is None:
    params = Params()
  return Context(env_name, app_name, params)


@pytest.mark.asyncio
async def test_DiscoverK8sKustomizeApplication__run__env_dir_layout(tmp_path, mocker):
  # standard overlay layout: base/ + env dir with kustomization
  env_name = 'dev'
  app_name = 'my_app'

  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'kustomization.yaml').write_text('resources: []')
  (base_dir / 'deployment.yaml').write_text('kind: Deployment')

  env_dir = tmp_path / env_name
  env_dir.mkdir()
  (env_dir / 'kustomization.yaml').write_text('resources: [../base]')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_kustomize_ctx(env_name, app_name)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_kustomize_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['kustomize_exec_dir']) == env_name
  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert f'{env_name}/kustomization.yaml' in origins
  assert f'base/kustomization.yaml' in origins
  assert f'base/deployment.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sKustomizeApplication__run__base_only_layout(tmp_path, mocker):
  # only base dir exists — no env overlay
  env_name = 'dev'
  app_name = 'my_app'

  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'kustomization.yaml').write_text('resources: []')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_kustomize_ctx(env_name, app_name)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_kustomize_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['kustomize_exec_dir']) == 'base'
  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert f'base/kustomization.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sKustomizeApplication__run__root_layout(tmp_path, mocker):
  # kustomization at root — no base or env dir
  env_name = 'dev'
  app_name = 'my_app'

  (tmp_path / 'kustomization.yaml').write_text('resources: []')
  (tmp_path / 'deployment.yaml').write_text('kind: Deployment')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_kustomize_ctx(env_name, app_name)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_kustomize_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['kustomize_exec_dir']) == '.'
  # search_subdirs is None for root layout, so all files are discovered
  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'kustomization.yaml' in origins
  assert 'deployment.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sKustomizeApplication__run__output_context_values(tmp_path, mocker):
  env_name = 'dev'
  app_name = 'my_app'

  (tmp_path / 'kustomization.yaml').write_text('resources: []')

  mock_config = _patch_config(mocker, tmp_dir='/my/tmp', output_dir='/my/output')
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_kustomize_ctx(env_name, app_name)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_kustomize_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['output_dir']) == '/my/output'
  assert ctx_get(ctx, stage.provides['tmp_dir']) == os.path.join('/my/tmp', default.KUSTOMIZE_DIR)
  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert f'kustomization.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sKustomizeApplication__run__resources_discovered_when_non_k8s_files_set(tmp_path, mocker):
  env_name = 'dev'
  app_name = 'my_app'

  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'kustomization.yaml').write_text('resources: []')
  (base_dir / 'values.yaml').write_text('key: value')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  params = Params()
  params.populate_params(non_k8s_files_to_render=['values.yaml'])
  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_kustomize_ctx(env_name, app_name, params)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_kustomize_stage()
  await stage.run(ctx)

  extra_resources = ctx_get(ctx, stage.provides['resources'])
  extra_origins = {r.origin for r in extra_resources}
  assert 'base/kustomization.yaml' in extra_origins
  assert 'base/values.yaml' in extra_origins

  assert ctx_get(ctx, stage.provides['templated_resources']) == []
  assert ctx_get(ctx, stage.provides['extra_resources']) == []
  assert ctx_get(ctx, stage.provides['templated_extra_resources']) == []


@pytest.mark.asyncio
async def test_DiscoverK8sKustomizeApplication__run__exclude_rendering_filters_resources(tmp_path, mocker):
  env_name = 'dev'
  app_name = 'my_app'

  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'kustomization.yaml').write_text('resources: []')
  (base_dir / 'secret.yaml').write_text('kind: Secret')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  params = Params()
  params.populate_params(exclude_rendering=['base/secret.yaml'])
  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_kustomize_ctx(env_name, app_name, params)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_kustomize_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'base/secret.yaml' not in origins
  assert 'base/kustomization.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sKustomizeApplication__run__common_dirs_included(tmp_path, mocker):
  env_name = 'dev'
  app_name = 'my_app'

  base_dir = tmp_path / 'base'
  base_dir.mkdir()
  (base_dir / 'kustomization.yaml').write_text('resources: []')

  env_dir = tmp_path / env_name
  env_dir.mkdir()
  (env_dir / 'kustomization.yaml').write_text('bases: [../base]')

  common_dir = tmp_path / 'common'
  common_dir.mkdir()
  (common_dir / 'patch.yaml').write_text('kind: Patch')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  params = Params()
  params.populate_params(kustomize_common_dirs=['common'])
  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_kustomize_ctx(env_name, app_name, params)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_kustomize_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'common/patch.yaml' in origins

###################
### _find_child_apps
###################

def _make_mock_config(apps_by_env: dict[str, dict]) -> MagicMock:
  """
  apps_by_env: { env_name: { app_name: Params } }
  """
  config = MagicMock()
  config.list_envs.return_value = list(apps_by_env.keys())

  def list_apps(env_name):
    return list(apps_by_env[env_name].keys())

  def get_params(env_name, app_name):
    return apps_by_env[env_name][app_name]

  config.list_apps.side_effect = list_apps
  config.get_params.side_effect = get_params
  return config


def _params_with_parent(parent_app: str, parent_app_env: str | None = None) -> Params:
  p = Params()
  p.populate_params(parent_app=parent_app,
                    **({'parent_app_env': parent_app_env} if parent_app_env else {}))
  return p


def test_find_child_apps__single_child_same_env():
  config = _make_mock_config({
    'env1': {
      'bootstrap': Params(),
      'app_1': _params_with_parent('bootstrap'),
    }
  })
  assert _find_child_apps(config, 'bootstrap', 'env1') == [('env1', 'app_1')]


def test_find_child_apps__multiple_children_same_env():
  config = _make_mock_config({
    'env1': {
      'bootstrap': Params(),
      'app_1': _params_with_parent('bootstrap'),
      'app_2': _params_with_parent('bootstrap'),
    }
  })
  result = _find_child_apps(config, 'bootstrap', 'env1')
  assert check_lists_equal(result, [('env1', 'app_1'), ('env1', 'app_2')])


def test_find_child_apps__child_in_different_env_with_explicit_parent_env():
  config = _make_mock_config({
    'env1': {
      'bootstrap': Params(),
    },
    'env2': {
      'app_1': _params_with_parent('bootstrap', parent_app_env='env1'),
    }
  })
  result = _find_child_apps(config, 'bootstrap', 'env1')
  assert result == [('env2', 'app_1')]


def test_find_child_apps__child_without_parent_app_env_only_matches_same_env():
  # parent_app_env=None means "same env as parent" — should NOT match if env differs
  config = _make_mock_config({
    'env1': {'bootstrap': Params()},
    'env2': {'app_1': _params_with_parent('bootstrap')},  # no parent_app_env
  })
  result = _find_child_apps(config, 'bootstrap', 'env1')
  assert result == []


def test_find_child_apps__no_children():
  config = _make_mock_config({
    'env1': {'bootstrap': Params(), 'app_1': Params()}  # app_1 has no parent_app
  })
  assert _find_child_apps(config, 'bootstrap', 'env1') == []


def test_find_child_apps__wrong_parent_name_not_matched():
  config = _make_mock_config({
    'env1': {
      'bootstrap': Params(),
      'other_bootstrap': Params(),
      'app_1': _params_with_parent('other_bootstrap'),
    }
  })
  assert _find_child_apps(config, 'bootstrap', 'env1') == []


def test_find_child_apps__explicit_parent_env_wrong_env_not_matched():
  # app_1 points to bootstrap in env2, not env1 — should not appear when querying env1
  config = _make_mock_config({
    'env1': {'bootstrap': Params()},
    'env2': {'bootstrap': Params()},
    'env3': {'app_1': _params_with_parent('bootstrap', parent_app_env='env2')},
  })
  assert _find_child_apps(config, 'bootstrap', 'env1') == []


def test_find_child_apps__multiple_envs_mixed():
  config = _make_mock_config({
    'env1': {
      'bootstrap': Params(),
      'app_1': _params_with_parent('bootstrap'),
    },
    'env2': {
      'app_2': _params_with_parent('bootstrap', parent_app_env='env1'),
      'app_3': _params_with_parent('bootstrap'),  # no parent_app_env — only matches env2 parent
    }
  })
  result = _find_child_apps(config, 'bootstrap', 'env1')
  assert check_lists_equal(result, [('env1', 'app_1'), ('env2', 'app_2')])

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
### DiscoverK8sHelmfileApplication.run()
###################

def _make_helmfile_stage():
  return DiscoverK8sHelmfileApplication(
    requires={'viewer': 'source.viewer'},
    provides={
      'resources': 'discovered.resources',
      'templated_resources': 'discovered.templated_resources',
      'tmp_dir': 'discovered.tmp_dir',
      'output_dir': 'discovered.output_dir',
    }
  )


@pytest.mark.asyncio
async def test_DiscoverK8sHelmfileApplication__run__yaml_files_discovered(tmp_path, mocker):
  (tmp_path / 'helmfile.yaml').write_text('releases: []')
  (tmp_path / 'values.yaml').write_text('key: value')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_helmfile_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'helmfile.yaml' in origins
  assert 'values.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sHelmfileApplication__run__j2_files_discovered_as_templated(tmp_path, mocker):
  (tmp_path / 'helmfile.yaml.j2').write_text('releases:\n  - name: {{ name }}')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_helmfile_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  templated = ctx_get(ctx, stage.provides['templated_resources'])
  assert {r.origin for r in resources} == set()
  assert 'helmfile.yaml.j2' in {r.origin for r in templated}


@pytest.mark.asyncio
async def test_DiscoverK8sHelmfileApplication__run__non_yaml_files_not_discovered(tmp_path, mocker):
  (tmp_path / 'helmfile.yaml').write_text('releases: []')
  (tmp_path / 'script.sh').write_text('#!/bin/bash')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_helmfile_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'script.sh' not in origins


@pytest.mark.asyncio
async def test_DiscoverK8sHelmfileApplication__run__exclude_rendering_filters_resources(tmp_path, mocker):
  (tmp_path / 'helmfile.yaml').write_text('releases: []')
  (tmp_path / 'secret.yaml').write_text('key: secret')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  params = Params()
  params.populate_params(exclude_rendering=['secret.yaml'])
  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app', params)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_helmfile_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'secret.yaml' not in origins
  assert 'helmfile.yaml' in origins


@pytest.mark.asyncio
async def test_DiscoverK8sHelmfileApplication__run__tmp_dir_and_output_dir_set(tmp_path, mocker):
  _patch_config(mocker, tmp_dir='/my/tmp', output_dir='/my/output')
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_helmfile_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['output_dir']) == '/my/output'
  assert ctx_get(ctx, stage.provides['tmp_dir']) == os.path.join('/my/tmp', default.HELMFILE_DIR)


###################
### DiscoverGenericApplication.run()
###################

def _make_generic_stage():
  return DiscoverGenericApplication(
    requires={'viewer': 'source.viewer'},
    provides={
      'resources': 'discovered.resources',
      'templated_resources': 'discovered.templated_resources',
      'output_dir': 'discovered.output_dir',
    }
  )


@pytest.mark.asyncio
async def test_DiscoverGenericApplication__run__all_file_types_discovered(tmp_path, mocker):
  # Generic discovers everything — yaml, txt, sh, json etc.
  (tmp_path / 'config.yaml').write_text('key: value')
  (tmp_path / 'cluster.yml').write_text('key: value')
  (tmp_path / 'readme.txt').write_text('some text')
  (tmp_path / 'setup.sh').write_text('#!/bin/bash')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_generic_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'config.yaml' in origins
  assert 'cluster.yml' in origins
  assert 'readme.txt' in origins
  assert 'setup.sh' in origins


@pytest.mark.asyncio
async def test_DiscoverGenericApplication__run__j2_files_in_templated_resources(tmp_path, mocker):
  (tmp_path / 'cluster.yml.j2').write_text('nodes: {{ node_count }}')
  (tmp_path / 'readme.txt').write_text('static content')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_generic_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  templated = ctx_get(ctx, stage.provides['templated_resources'])
  assert 'readme.txt' in {r.origin for r in resources}
  assert 'cluster.yml.j2' not in {r.origin for r in resources}
  assert 'cluster.yml.j2' in {r.origin for r in templated}


@pytest.mark.asyncio
async def test_DiscoverGenericApplication__run__exclude_rendering_filters_all_types(tmp_path, mocker):
  (tmp_path / 'cluster.yml').write_text('key: value')
  (tmp_path / 'secret.txt').write_text('password=hunter2')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  params = Params()
  params.populate_params(exclude_rendering=['secret.txt'])
  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app', params)
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_generic_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'secret.txt' not in origins
  assert 'cluster.yml' in origins


@pytest.mark.asyncio
async def test_DiscoverGenericApplication__run__subdirectory_files_discovered(tmp_path, mocker):
  subdir = tmp_path / 'infra'
  subdir.mkdir()
  (subdir / 'cluster.yml').write_text('key: value')
  (subdir / 'notes.txt').write_text('some notes')

  _patch_config(mocker)
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_generic_stage()
  await stage.run(ctx)

  resources = ctx_get(ctx, stage.provides['resources'])
  origins = {r.origin for r in resources}
  assert 'infra/cluster.yml' in origins
  assert 'infra/notes.txt' in origins


@pytest.mark.asyncio
async def test_DiscoverGenericApplication__run__output_dir_set_from_config(tmp_path, mocker):
  _patch_config(mocker, output_dir='/generic/output')
  _patch_template_vars(mocker)

  viewer = build_scoped_viewer(tmp_path)
  ctx = _make_simple_ctx('dev', 'my_app')
  ctx_set(ctx, 'source.viewer', viewer)

  stage = _make_generic_stage()
  await stage.run(ctx)

  assert ctx_get(ctx, stage.provides['output_dir']) == '/generic/output'

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
  mocker.patch('make_argocd_fly.stage._base.get_config', mock_get_config)
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

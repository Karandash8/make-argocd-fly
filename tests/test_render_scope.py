import textwrap

from make_argocd_fly.cliparam import populate_cli_params
from make_argocd_fly.config import populate_config
from make_argocd_fly.render_scope import RenderScope, build_render_scope


CONFIG = '''\
  envs:
    dev:
      apps:
        app1: {}
        app2: {}
        monitoring/prometheus: {}
    staging:
      apps:
        app1: {}
        app3: {}
    prod:
      apps:
        app1: {}
'''


def _setup_config(tmp_path, config_yaml: str = CONFIG, render_envs: str | None = None, render_apps: str | None = None):
  config_dir = tmp_path / 'config'
  config_dir.mkdir()
  (config_dir / 'config.yml').write_text(textwrap.dedent(config_yaml))

  source_dir = tmp_path / 'source'
  source_dir.mkdir()

  populate_cli_params(render_envs=render_envs, render_apps=render_apps, skip_latest_version_check=True)
  return populate_config(root_dir=tmp_path, config_dir=config_dir, source_dir=source_dir)


def test_build_render_scope__full_render_returns_root_scope(tmp_path):
  config = _setup_config(tmp_path)

  render_scope = build_render_scope(config, full_run=True)

  assert isinstance(render_scope, RenderScope)
  assert render_scope.full_run is True
  assert render_scope.output_scopes == ['.']


def test_build_render_scope__full_render_lists_all_selected_apps(tmp_path):
  config = _setup_config(tmp_path)

  render_scope = build_render_scope(config, full_run=True)

  assert render_scope.selected_apps == {
    ('dev', 'app1'),
    ('dev', 'app2'),
    ('dev', 'monitoring/prometheus'),
    ('staging', 'app1'),
    ('staging', 'app3'),
    ('prod', 'app1')
  }


def test_build_render_scope__full_render_selected_apps_ignore_active_filters(tmp_path):
  config = _setup_config(tmp_path, render_envs='dev', render_apps='app2')

  render_scope = build_render_scope(config, full_run=True)

  assert render_scope.output_scopes == ['.']
  assert render_scope.selected_apps == {
    ('dev', 'app1'),
    ('dev', 'app2'),
    ('dev', 'monitoring/prometheus'),
    ('staging', 'app1'),
    ('staging', 'app3'),
    ('prod', 'app1')
  }


def test_build_render_scope__render_envs_limits_selected_apps_and_scopes(tmp_path):
  config = _setup_config(tmp_path, render_envs='dev')

  render_scope = build_render_scope(config, full_run=False)

  assert render_scope.full_run is False
  assert render_scope.selected_apps == {
    ('dev', 'app1'),
    ('dev', 'app2'),
    ('dev', 'monitoring/prometheus')
  }
  assert render_scope.output_scopes == ['dev/app1', 'dev/app2', 'dev/monitoring/prometheus']


def test_build_render_scope__render_apps_limits_selected_apps_and_scopes(tmp_path):
  config = _setup_config(tmp_path, render_apps='app1')

  render_scope = build_render_scope(config, full_run=False)

  assert render_scope.selected_apps == {
    ('dev', 'app1'),
    ('staging', 'app1'),
    ('prod', 'app1')
  }
  assert render_scope.output_scopes == ['dev/app1', 'staging/app1', 'prod/app1']


def test_build_render_scope__combined_render_envs_and_render_apps(tmp_path):
  config = _setup_config(tmp_path, render_envs='dev,prod', render_apps='app1')

  render_scope = build_render_scope(config, full_run=False)

  assert render_scope.selected_apps == {
    ('dev', 'app1'),
    ('prod', 'app1')
  }
  assert render_scope.output_scopes == ['dev/app1', 'prod/app1']


def test_build_render_scope__glob_patterns_use_existing_config_filtering(tmp_path):
  config = _setup_config(tmp_path, render_envs='sta*', render_apps='app*')

  render_scope = build_render_scope(config, full_run=False)

  assert render_scope.selected_apps == {
    ('staging', 'app1'),
    ('staging', 'app3')
  }
  assert render_scope.output_scopes == ['staging/app1', 'staging/app3']


def test_build_render_scope__nested_app_names_produce_nested_output_scopes(tmp_path):
  config = _setup_config(tmp_path, render_apps='monitoring/*')

  render_scope = build_render_scope(config, full_run=False)

  assert render_scope.selected_apps == {('dev', 'monitoring/prometheus')}
  assert render_scope.output_scopes == ['dev/monitoring/prometheus']


def test_build_render_scope__no_matching_filters_returns_empty_partial_scope(tmp_path):
  config = _setup_config(tmp_path, render_envs='missing*')

  render_scope = build_render_scope(config, full_run=False)

  assert render_scope.selected_apps == set()
  assert render_scope.output_scopes == []


def test_build_render_scope__output_scope_order_is_deterministic(tmp_path):
  config = _setup_config(tmp_path, render_envs='dev,staging', render_apps='app1,app3')

  render_scope = build_render_scope(config, full_run=False)

  assert render_scope.output_scopes == ['dev/app1', 'staging/app1', 'staging/app3']

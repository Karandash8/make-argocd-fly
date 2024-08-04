import pytest
import textwrap

from make_argocd_fly.steps import FindAppsStep
from make_argocd_fly.config import read_config
from make_argocd_fly.cli_args import populate_cli_args

###################
### FindAppsStep
###################

@pytest.fixture
def find_apps_step():
  return FindAppsStep()

# @pytest.fixture
# def get_config():

def test_find_apps_step_configure(find_apps_step):
  app_deployer_name = "my_app_deployer"
  app_deployer_env_name = "my_env"

  find_apps_step.configure(app_deployer_name, app_deployer_env_name)

  assert find_apps_step.app_deployer_name == app_deployer_name
  assert find_apps_step.app_deployer_env_name == app_deployer_env_name

def test_find_apps_step_get_apps(find_apps_step):
  apps = find_apps_step.get_apps()

  assert isinstance(apps, list)
  assert len(apps) == 0

@pytest.mark.asyncio
async def test_find_apps_step_run_single_app_same_env(tmp_path):
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
  cli_args = populate_cli_args(root_dir=root_dir, config_file=config_file, source_dir=source_dir, output_dir='output', tmp_dir='.tmp')
  read_config(root_dir, config_file, cli_args)

  app_deployer_name = "bootstrap"
  app_deployer_env_name = "test_env"
  find_apps_step = FindAppsStep()
  find_apps_step.configure(app_deployer_name, app_deployer_env_name)

  await find_apps_step.run()
  apps = find_apps_step.get_apps()

  assert isinstance(apps, list)
  assert len(apps) == 1
  assert ('app_1', 'test_env') in apps

@pytest.mark.asyncio
async def test_find_apps_step_run_multiple_apps_same_env(tmp_path):
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
  cli_args = populate_cli_args(root_dir=root_dir, config_file=config_file, source_dir=source_dir, output_dir='output', tmp_dir='.tmp')
  read_config(root_dir, config_file, cli_args)

  app_deployer_name = "bootstrap"
  app_deployer_env_name = "test_env"
  find_apps_step = FindAppsStep()
  find_apps_step.configure(app_deployer_name, app_deployer_env_name)

  await find_apps_step.run()
  apps = find_apps_step.get_apps()

  assert isinstance(apps, list)
  assert len(apps) == 2
  assert ('app_1', 'test_env') in apps
  assert ('app_2', 'test_env') in apps

@pytest.mark.asyncio
async def test_find_apps_step_run_multiple_apps_different_envs(tmp_path):
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
  cli_args = populate_cli_args(root_dir=root_dir, config_file=config_file, source_dir=source_dir, output_dir='output', tmp_dir='.tmp')
  read_config(root_dir, config_file, cli_args)

  app_deployer_name = "bootstrap"
  app_deployer_env_name = "test_env"
  find_apps_step = FindAppsStep()
  find_apps_step.configure(app_deployer_name, app_deployer_env_name)

  await find_apps_step.run()
  apps = find_apps_step.get_apps()

  assert isinstance(apps, list)
  assert len(apps) == 2
  assert ('app_1', 'test_env') in apps
  assert ('app_2', 'test_env_2') in apps

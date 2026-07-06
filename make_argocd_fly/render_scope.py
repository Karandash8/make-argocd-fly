from dataclasses import dataclass

from make_argocd_fly.config import Config
from make_argocd_fly.util import get_app_rel_path


@dataclass
class RenderScope:
  full_run: bool
  selected_apps: set[tuple[str, str]]
  output_scopes: list[str]


def build_render_scope(config: Config, full_run: bool) -> RenderScope:
  envs = config.list_envs() if full_run else config.list_filtered_envs()
  selected_app_list = [
    (env_name, app_name)
    for env_name in envs
    for app_name in (config.list_apps(env_name) if full_run else config.list_filtered_apps(env_name))
  ]

  if full_run:
    output_scopes = ['.']
  else:
    output_scopes = [
      get_app_rel_path(env_name, app_name)
      for env_name, app_name in selected_app_list
    ]

  return RenderScope(
    full_run=full_run,
    selected_apps=set(selected_app_list),
    output_scopes=output_scopes
  )

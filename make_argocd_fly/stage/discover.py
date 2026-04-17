import logging
import os
import textwrap

from make_argocd_fly.context import Context, ctx_get, ctx_set
from make_argocd_fly.context.data import TemplatedResource
from make_argocd_fly.resource.viewer import ResourceType
from make_argocd_fly import default
from make_argocd_fly.param import ParamNames
from make_argocd_fly.config import get_config, Config
from make_argocd_fly.exception import InternalError, ConfigFileError
from make_argocd_fly.util import ensure_list
from make_argocd_fly.stage._base import (
  _resolve_template_vars,
  _discover_resources,
  _discover_templated_resources,
  _discover_extra_resources,
  _discover_templated_extra_resources,
)


log = logging.getLogger(__name__)


class DiscoverK8sSimpleApplication:
  name = 'DiscoverK8sSimpleApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)
    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    out_resources = _discover_resources(viewer,
                                        resource_types=[ResourceType.YAML],
                                        search_subdirs=None,
                                        excludes=exclude_rendering)
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=[ResourceType.YAML],
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=None,
                                                            excludes=exclude_rendering)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['output_dir'], config.runtime_output_dir)


class DiscoverK8sKustomizeApplication:
  name = 'DiscoverK8sKustomizeApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    # Determine search_subdirs:
    # look for root-level "base" and "<env_name>" directories; if none exist, use None
    candidate_subdirs: list[str] = []

    if any(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY],
                                      name_pattern=r'^base$',
                                      depth=1)):
      candidate_subdirs.append('base')

    if any(viewer.search_subresources(resource_types=[ResourceType.DIRECTORY],
                                      name_pattern=fr'^{ctx.env_name}$',
                                      depth=1)):
      candidate_subdirs.append(ctx.env_name)

    if candidate_subdirs:
      kustomize_common_dirs = ensure_list(ctx.params.kustomize_common_dirs, ParamNames.KUSTOMIZE_COMMON_DIRS)
      for common_dir in kustomize_common_dirs:
        if viewer.exists(common_dir):
          candidate_subdirs.append(common_dir)
        else:
          log.warning(f'kustomize_common_dirs entry `{common_dir}` does not exist in application '
                      f'`{ctx.app_name}`, skipping')

    search_subdirs = list(set(candidate_subdirs)) or None

    non_k8s_files = ensure_list(ctx.params.non_k8s_files_to_render, ParamNames.NON_K8S_FILES_TO_RENDER)
    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)

    # 1) regular YAML resources (non-template), exclude both lists
    out_resources = _discover_resources(viewer,
                                        resource_types=[ResourceType.YAML],
                                        search_subdirs=search_subdirs,
                                        excludes=exclude_rendering + non_k8s_files)

    # 2) regular YAML templated resources, exclude both lists
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=[ResourceType.YAML],
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=search_subdirs,
                                                            excludes=exclude_rendering + non_k8s_files)

    all_file_types = [resource_type for resource_type in ResourceType if
                      (resource_type != ResourceType.DIRECTORY and
                       resource_type != ResourceType.DOES_NOT_EXIST)]

    out_extra_resources = []
    out_templated_extra_resources = []
    if non_k8s_files:
      # 3) extra resources: include only non_k8s_files_to_render (any file type), exclude exclude_rendering
      out_extra_resources = _discover_extra_resources(viewer,
                                                      resource_types=all_file_types,
                                                      search_subdirs=search_subdirs,
                                                      excludes=exclude_rendering,
                                                      includes=non_k8s_files)

      # 4) templated extra resources: include only non_k8s_files_to_render (any file type), exclude exclude_rendering
      out_templated_extra_resources = _discover_templated_extra_resources(viewer,
                                                                          resource_types=all_file_types,
                                                                          resolved_vars=resolved_vars,
                                                                          search_subdirs=search_subdirs,
                                                                          excludes=exclude_rendering,
                                                                          includes=non_k8s_files)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['extra_resources'], out_extra_resources)
    ctx_set(ctx, self.provides['templated_extra_resources'], out_templated_extra_resources)
    ctx_set(ctx, self.provides['tmp_dir'], os.path.join(config.tmp_dir, default.KUSTOMIZE_DIR))
    ctx_set(ctx, self.provides['output_dir'], config.runtime_output_dir)

    if list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                       name_pattern='kustomization|Kustomization',
                                       search_subdirs=[ctx.env_name],
                                       depth=1)):
      kustomize_exec_dir = ctx.env_name
    elif list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                         name_pattern='kustomization|Kustomization',
                                         search_subdirs=['base'],
                                         depth=1)):
      kustomize_exec_dir = 'base'
    elif list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                         name_pattern='kustomization|Kustomization',
                                         depth=1)):
      kustomize_exec_dir = '.'
    else:
      raise InternalError(f'Missing kustomization in the application directory. Skipping application `{ctx.app_name}` '
                          f'in environment `{ctx.env_name}`')

    ctx_set(ctx, self.provides['kustomize_exec_dir'], kustomize_exec_dir)


class DiscoverK8sHelmfileApplication:
  name = 'DiscoverK8sHelmfileApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)
    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    out_resources = _discover_resources(viewer,
                                        resource_types=[ResourceType.YAML],
                                        search_subdirs=None,
                                        excludes=exclude_rendering)
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=[ResourceType.YAML],
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=None,
                                                            excludes=exclude_rendering)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['tmp_dir'], os.path.join(config.tmp_dir, default.HELMFILE_DIR))
    ctx_set(ctx, self.provides['output_dir'], config.runtime_output_dir)


def _find_child_apps(config: Config, parent_app_name: str, parent_env_name: str) -> list[tuple[str, str]]:
  """Return (env_name, app_name) pairs for all apps that declare parent_app_name as their parent."""
  discovered = []
  for env_name in config.list_envs():
    for app_name in config.list_apps(env_name):
      params = config.get_params(env_name, app_name)

      if not params.parent_app:
        continue

      parent_matches = params.parent_app == parent_app_name
      env_matches = (
        (params.parent_app_env is None and env_name == parent_env_name) or
        (params.parent_app_env is not None and params.parent_app_env == parent_env_name)
      )

      if parent_matches and env_matches:
        discovered.append((env_name, app_name))

  return discovered


class DiscoverK8sAppOfAppsApplication:
  name = 'DiscoverK8sAppOfAppsApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()

    child_apps = _find_child_apps(config, ctx.app_name, ctx.env_name)

    out_templated_resources = []
    for env_name, app_name in child_apps:
      resolved_vars = _resolve_template_vars(env_name, app_name)

      try:
        out_templated_resources.append(TemplatedResource(
          resource_type=ResourceType.YAML,
          vars=resolved_vars,
          data=textwrap.dedent(resolved_vars['argocd_application_cr_template']),
          origin='Application',
          source_path=None,
        ))
      except TypeError:
        raise ConfigFileError(f'Error rendering Jinja template for application `{ctx.app_name}` in environment `{ctx.env_name}`. '
                              f'Ensure that the template is correctly defined in the config file.')

    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['output_dir'], config.runtime_output_dir)


class DiscoverGenericApplication:
  name = 'DiscoverGenericApplication'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    config = get_config()
    viewer = ctx_get(ctx, self.requires['viewer'])

    exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)
    resolved_vars = _resolve_template_vars(ctx.env_name, ctx.app_name)

    all_file_types = [resource_type for resource_type in ResourceType if
                      (resource_type != ResourceType.DIRECTORY and
                       resource_type != ResourceType.DOES_NOT_EXIST)]

    out_resources = _discover_resources(viewer,
                                        resource_types=all_file_types,
                                        search_subdirs=None,
                                        excludes=exclude_rendering)
    out_templated_resources = _discover_templated_resources(viewer,
                                                            resource_types=all_file_types,
                                                            resolved_vars=resolved_vars,
                                                            search_subdirs=None,
                                                            excludes=exclude_rendering)

    ctx_set(ctx, self.provides['resources'], out_resources)
    ctx_set(ctx, self.provides['templated_resources'], out_templated_resources)
    ctx_set(ctx, self.provides['output_dir'], config.runtime_output_dir)

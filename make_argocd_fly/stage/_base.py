import logging
import os
from typing import Protocol, Iterable
from pprint import pformat
from deprecated import deprecated

from make_argocd_fly.context import Context
from make_argocd_fly.context.data import TemplatedResource, Resource
from make_argocd_fly.resource.viewer import ScopedViewer, ResourceType
from make_argocd_fly import default
from make_argocd_fly.param import ApplicationNameFormat
from make_argocd_fly.config import get_config
from make_argocd_fly.cliparam import get_cli_params


log = logging.getLogger(__name__)


class Stage(Protocol):
  name: str
  requires: dict[str, str]
  provides: dict[str, str]

  async def run(self, ctx: Context) -> None: ...


@deprecated(version='v0.4.4', reason='`--print-vars` is deprecated, use `--dump-context` instead')
def print_vars_deprecated(app_name: str, env_name: str, vars_: dict) -> None:
  log.info(f'Variables for application {app_name} in environment {env_name}:\n{pformat(vars_)}')


def _resolve_template_vars(env_name: str, app_name: str) -> dict:
  config = get_config()
  params = config.get_params(env_name, app_name)

  if params.application_name == ApplicationNameFormat.FULL:
    name_segment = app_name.replace('/', '-')
  else:
    name_segment = os.path.basename(app_name)

  extra = {
    'argocd_application_cr_template': default.ARGOCD_APPLICATION_CR_TEMPLATE,
    '__application': {
      'application_name': f'{name_segment}-{env_name}'.replace('_', '-'),
      'path': os.path.join(os.path.basename(config.final_output_dir), env_name, app_name)
    },
    'argocd': default.ARGOCD_DEFAULTS,
    'env_name': env_name,
    'app_name': app_name,
  }
  vars_ = config.get_vars(env_name=env_name, app_name=app_name, extra_vars=extra)

  if get_cli_params().print_vars:
    print_vars_deprecated(app_name, env_name, vars_)

  return vars_


def _discover_resources(viewer: ScopedViewer,
                        resource_types: list[ResourceType],
                        *,
                        search_subdirs: list[str] | None,
                        excludes: Iterable[str] | None) -> list[Resource]:
  out_resources = []
  for child in viewer.search_subresources(resource_types=resource_types,
                                          template=False,
                                          search_subdirs=search_subdirs,
                                          excludes=excludes):
    out_resources.append(Resource(resource_type=child.resource_type,
                                  data=child.content,
                                  origin=child.rel_path,
                                  source_path=child.rel_path))

  return out_resources


def _discover_templated_resources(viewer: ScopedViewer,
                                  resource_types: list[ResourceType],
                                  resolved_vars: dict,
                                  *,
                                  search_subdirs: list[str] | None,
                                  excludes: Iterable[str] | None) -> list[TemplatedResource]:
  out_templated_resources = []
  for child in viewer.search_subresources(resource_types=resource_types,
                                          template=True,
                                          search_subdirs=search_subdirs,
                                          excludes=excludes):
    out_templated_resources.append(TemplatedResource(resource_type=child.resource_type,
                                                     vars=resolved_vars,
                                                     data=child.content,
                                                     origin=child.rel_path,
                                                     source_path=child.rel_path))

  return out_templated_resources


def _discover_extra_resources(viewer: ScopedViewer,
                              resource_types: list[ResourceType],
                              *,
                              search_subdirs: list[str] | None,
                              excludes: Iterable[str] | None,
                              includes: Iterable[str] | None) -> list[Resource]:
  out_extra_resources = []
  for child in viewer.search_subresources(resource_types=resource_types,
                                          template=False,
                                          search_subdirs=search_subdirs,
                                          excludes=excludes,
                                          includes=includes):
    out_extra_resources.append(Resource(resource_type=child.resource_type,
                                        data=child.content,
                                        origin=child.rel_path,
                                        source_path=child.rel_path))

  return out_extra_resources


def _discover_templated_extra_resources(viewer: ScopedViewer,
                                        resource_types: list[ResourceType],
                                        resolved_vars: dict,
                                        *,
                                        search_subdirs: list[str] | None,
                                        excludes: Iterable[str] | None,
                                        includes: Iterable[str] | None) -> list[TemplatedResource]:
  out_templated_extra_resources = []
  for child in viewer.search_subresources(resource_types=resource_types,
                                          template=True,
                                          search_subdirs=search_subdirs,
                                          excludes=excludes,
                                          includes=includes):
    out_templated_extra_resources.append(TemplatedResource(resource_type=child.resource_type,
                                                           vars=resolved_vars,
                                                           data=child.content,
                                                           origin=child.rel_path,
                                                           source_path=child.rel_path))

  return out_templated_extra_resources

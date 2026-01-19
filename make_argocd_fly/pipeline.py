import logging
import time
import inspect
from dataclasses import dataclass

from make_argocd_fly.context import Context, ctx_set
from make_argocd_fly.stage import Stage
from make_argocd_fly.config import get_config
from make_argocd_fly.param import ApplicationTypes, ParamNames
from make_argocd_fly.exception import ConfigFileError, PathDoesNotExistError
from make_argocd_fly.resource.viewer import ResourceType, ScopedViewer
from make_argocd_fly.stage import (DiscoverK8sSimpleApplication, DiscoverK8sKustomizeApplication, DiscoverK8sHelmfileApplication,
                                   DiscoverK8sAppOfAppsApplication, DiscoverGenericApplication, RenderTemplates, SplitManifests,
                                   WriteOnDisk, KustomizeBuild, HelmfileRun, GenerateNames,
                                   ConvertToYaml)
from make_argocd_fly.limits import RuntimeLimits
from make_argocd_fly.type import PipelineType
from make_argocd_fly.util import ensure_list
from make_argocd_fly.cliparam import get_cli_params
from make_argocd_fly.debug_dump import StageContextDumper


log = logging.getLogger(__name__)


class Pipeline:
  def __init__(self, type: PipelineType, stages: list[Stage]):
    self.type = type
    self.stages = stages

  async def run(self, ctx: Context):
    cli = get_cli_params()
    dumper = StageContextDumper(enabled=cli.dump_context, ctx=ctx)

    for idx, stage in enumerate(self.stages):
      # TODO: pre-validate: ensure required keys are present

      t0 = time.perf_counter()
      try:
        await stage.run(ctx)
      except Exception as e:
        dumper.dump_error(ctx, stage, e)
        raise
      t1 = time.perf_counter()

      # TODO: post-validate: ensure provided keys are present
      ctx.trace.append({
        'stage': stage.name,
        'index': idx,
        'ms': (t1 - t0) * 1000.0,
      })
      dumper.dump_success(ctx, stage)

    log.info(f'Updated application {ctx.app_name} in environment {ctx.env_name}')


@dataclass(frozen=True)
class StageSpec:
  cls: type[Stage]
  requires: dict[str, str]
  provides: dict[str, str]
  kwargs: dict[str, object] | None = None


PIPELINES: dict[PipelineType, list[StageSpec]] = {
  PipelineType.K8S_SIMPLE: [
    StageSpec(cls=DiscoverK8sSimpleApplication,
              requires={'viewer': 'source.viewer'},
              provides={'resources': 'discovered.resources',
                        'templated_resources': 'discovered.templated_resources',
                        'output_dir': 'discovered.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'templated_resources': 'discovered.templated_resources'},
              provides={'resources': 'rendered.resources'}),
    StageSpec(cls=SplitManifests,
              requires={'resources': 'discovered.resources&rendered.resources'},
              provides={'resources': 'split.resources'}),
    StageSpec(cls=ConvertToYaml,
              requires={'resources': 'split.resources'},
              provides={'resources': 'converted.resources'}),
    StageSpec(cls=GenerateNames,
              requires={'resources': 'converted.resources'},
              provides={'resources': 'named.resources'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'resources': 'named.resources',
                        'output_dir': 'discovered.output_dir'},
              provides={},
              kwargs={'limits': None}),
  ],
  PipelineType.K8S_KUSTOMIZE: [
    StageSpec(cls=DiscoverK8sKustomizeApplication,
              requires={'viewer': 'source.viewer'},
              provides={'resources': 'discovered.resources',
                        'templated_resources': 'discovered.templated_resources',
                        'extra_resources': 'discovered.extra_resources',
                        'templated_extra_resources': 'discovered.templated_extra_resources',
                        'kustomize_exec_dir': 'discovered.kustomize_exec_dir',
                        'tmp_dir': 'discovered.tmp_dir',
                        'output_dir': 'discovered.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'templated_resources': 'discovered.templated_resources'},
              provides={'resources': 'rendered.resources'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'templated_resources': 'discovered.templated_extra_resources'},
              provides={'resources': 'rendered.extra_resources'}),
    StageSpec(cls=SplitManifests,
              requires={'resources': 'discovered.resources&rendered.resources'},
              provides={'resources': 'staging.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'resources': 'staging.raw'},
              provides={'resources': 'staging.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'resources': 'staging.parsed&discovered.extra_resources&rendered.extra_resources'},
              provides={'resources': 'generated.tmp_files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'resources': 'generated.tmp_files',
                        'output_dir': 'discovered.tmp_dir'},
              provides={},
              kwargs={'limits': None}),
    StageSpec(cls=KustomizeBuild,
              requires={'kustomize_exec_dir': 'discovered.kustomize_exec_dir',
                        'tmp_dir': 'discovered.tmp_dir'},
              provides={'resources': 'kustomize.resources'},
              kwargs={'limits': None}),
    StageSpec(cls=SplitManifests,
              requires={'resources': 'kustomize.resources'},
              provides={'resources': 'split.resources'}),
    StageSpec(cls=ConvertToYaml,
              requires={'resources': 'split.resources'},
              provides={'resources': 'converted.resources'}),
    StageSpec(cls=GenerateNames,
              requires={'resources': 'converted.resources'},
              provides={'resources': 'named.resources'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'resources': 'named.resources',
                        'output_dir': 'discovered.output_dir'},
              provides={},
              kwargs={'limits': None})
  ],
  PipelineType.K8S_HELMFILE: [
    StageSpec(cls=DiscoverK8sHelmfileApplication,
              requires={'viewer': 'source.viewer'},
              provides={'resources': 'discovered.resources',
                        'templated_resources': 'discovered.templated_resources',
                        'tmp_dir': 'discovered.tmp_dir',
                        'output_dir': 'discovered.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'templated_resources': 'discovered.templated_resources'},
              provides={'resources': 'rendered.resources'}),
    StageSpec(cls=SplitManifests,
              requires={'resources': 'discovered.resources&rendered.resources'},
              provides={'resources': 'staging.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'resources': 'staging.raw'},
              provides={'resources': 'staging.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'resources': 'staging.parsed'},
              provides={'resources': 'generated.tmp_files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'resources': 'generated.tmp_files',
                        'output_dir': 'discovered.tmp_dir'},
              provides={},
              kwargs={'limits': None}),
    StageSpec(cls=HelmfileRun,
              requires={'tmp_dir': 'discovered.tmp_dir'},
              provides={'resources': 'helmfile.resources'},
              kwargs={'limits': None}),
    StageSpec(cls=SplitManifests,
              requires={'resources': 'helmfile.resources'},
              provides={'resources': 'split.resources'}),
    StageSpec(cls=ConvertToYaml,
              requires={'resources': 'split.resources'},
              provides={'resources': 'converted.resources'}),
    StageSpec(cls=GenerateNames,
              requires={'resources': 'converted.resources'},
              provides={'resources': 'named.resources'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'resources': 'named.resources',
                        'output_dir': 'discovered.output_dir'},
              provides={},
              kwargs={'limits': None})
  ],
  PipelineType.K8S_APP_OF_APPS: [
    StageSpec(cls=DiscoverK8sAppOfAppsApplication,
              requires={},
              provides={'templated_resources': 'discovered.templated_resources',
                        'output_dir': 'discovered.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'templated_resources': 'discovered.templated_resources'},
              provides={'resources': 'rendered.resources'}),
    StageSpec(cls=SplitManifests,
              requires={'resources': 'rendered.resources'},
              provides={'resources': 'split.resources'}),
    StageSpec(cls=ConvertToYaml,
              requires={'resources': 'split.resources'},
              provides={'resources': 'converted.resources'}),
    StageSpec(cls=GenerateNames,
              requires={'resources': 'converted.resources'},
              provides={'resources': 'named.resources'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'resources': 'named.resources',
                        'output_dir': 'discovered.output_dir'},
              provides={},
              kwargs={'limits': None}),
  ],
  PipelineType.GENERIC: [
    StageSpec(cls=DiscoverGenericApplication,
              requires={'viewer': 'source.viewer'},
              provides={'resources': 'discovered.resources',
                        'templated_resources': 'discovered.templated_resources',
                        'output_dir': 'discovered.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'templated_resources': 'discovered.templated_resources'},
              provides={'resources': 'rendered.resources'}),
    StageSpec(cls=GenerateNames,
              requires={'resources': 'discovered.resources&rendered.resources'},
              provides={'resources': 'named.resources'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'resources': 'named.resources',
                        'output_dir': 'discovered.output_dir'},
              provides={},
              kwargs={'limits': None}),
  ],
}


def _build_pipeline(kind: PipelineType, limits: RuntimeLimits) -> Pipeline:
  stages = []
  base_kwargs = {'pipeline_kind': kind, 'limits': limits}
  for spec in PIPELINES[kind]:
    sig = inspect.signature(spec.cls.__init__)
    allowed = {k: v for k, v in (spec.kwargs or {}).items() if k in sig.parameters}

    for k, v in base_kwargs.items():
      if k in sig.parameters:
        allowed[k] = v
    stage = spec.cls(requires=spec.requires, provides=spec.provides, **allowed)
    stages.append(stage)

  return Pipeline(kind, stages)


def build_pipeline(ctx: Context, limits: RuntimeLimits, viewer: ScopedViewer) -> Pipeline:
  config = get_config()

  if ctx.params.app_type == ApplicationTypes.K8S:
    try:
      viewer = viewer.go_to(ctx.app_name)
      ctx_set(ctx, 'source.viewer', viewer)

      exclude_rendering = ensure_list(ctx.params.exclude_rendering, ParamNames.EXCLUDE_RENDERING)
      kustomize_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                                           name_pattern='kustomization|Kustomization',
                                                           search_subdirs=['.', 'base'] + config.list_envs(),
                                                           depth=1,
                                                           excludes=exclude_rendering))
      helmfile_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                                          name_pattern='helmfile',
                                                          depth=1,
                                                          excludes=exclude_rendering))
      if kustomize_children:
        return _build_pipeline(PipelineType.K8S_KUSTOMIZE, limits)
      elif helmfile_children:
        return _build_pipeline(PipelineType.K8S_HELMFILE, limits)
      else:
        return _build_pipeline(PipelineType.K8S_SIMPLE, limits)
    except PathDoesNotExistError:
      return _build_pipeline(PipelineType.K8S_APP_OF_APPS, limits)
  elif ctx.params.app_type == ApplicationTypes.GENERIC:
    viewer = viewer.go_to(ctx.app_name)
    ctx_set(ctx, 'source.viewer', viewer)

    return _build_pipeline(PipelineType.GENERIC, limits)
  else:
    log.error(f'Unknown application type \'{ctx.params.app_type}\' in application {ctx.app_name} in environment {ctx.env_name}.'
              f' Valid types are: {[t.value for t in ApplicationTypes]}')
    raise ConfigFileError()

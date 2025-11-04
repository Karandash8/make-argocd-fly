import logging
import time
import inspect
from dataclasses import dataclass

from make_argocd_fly.context import Context, ctx_set
from make_argocd_fly.stage import Stage
from make_argocd_fly.config import get_config
from make_argocd_fly.param import ApplicationTypes
from make_argocd_fly.exception import ConfigFileError, PathDoesNotExistError
from make_argocd_fly.resource.viewer import ResourceType, ScopedViewer
from make_argocd_fly.stage import (DiscoverK8sSimpleApplication, DiscoverK8sKustomizeApplication, DiscoverK8sHelmfileApplication,
                                   DiscoverK8sAppOfAppsApplication, DiscoverGenericApplication, RenderTemplates, SplitManifests,
                                   WriteOnDisk, KustomizeBuild, HelmfileRun, GenerateNames,
                                   ConvertToYaml)
from make_argocd_fly.limits import RuntimeLimits
from make_argocd_fly.type import PipelineType


log = logging.getLogger(__name__)


class Pipeline:
  def __init__(self, type: PipelineType, stages: list[Stage]):
    self.type = type
    self.stages = stages

  async def run(self, ctx: Context):
    for s in self.stages:
      # TODO: pre-validate: ensure required keys are present

      t0 = time.perf_counter()
      await s.run(ctx)
      t1 = time.perf_counter()

      # TODO: post-validate: ensure provided keys are present

      ctx.trace.append({'stage': s.name, 'ms': (t1 - t0) * 1000.0})

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
              provides={'content': 'discover.content',
                        'template': 'discover.template',
                        'output_dir': 'discover.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'template': 'discover.template'},
              provides={'content': 'template.content'}),
    StageSpec(cls=SplitManifests,
              requires={'content': 'discover.content&template.content'},
              provides={'content': 'manifests.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'content': 'manifests.raw'},
              provides={'content': 'manifests.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'content': 'manifests.parsed'},
              provides={'files': 'generated.files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'files': 'generated.files',
                        'output_dir': 'discover.output_dir'},
              provides={},
              kwargs={'limits': None}),
  ],
  PipelineType.K8S_KUSTOMIZE: [
    StageSpec(cls=DiscoverK8sKustomizeApplication,
              requires={'viewer': 'source.viewer'},
              provides={'content': 'discover.content',
                        'template': 'discover.template',
                        'kustomize_exec_dir': 'discover.kustomize_exec_dir',
                        'tmp_dir': 'discover.tmp_dir',
                        'output_dir': 'discover.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'template': 'discover.template'},
              provides={'content': 'template.content'}),
    StageSpec(cls=SplitManifests,
              requires={'content': 'discover.content&template.content'},
              provides={'content': 'staging.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'content': 'staging.raw'},
              provides={'content': 'staging.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'content': 'staging.parsed'},
              provides={'files': 'generated.tmp_files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'files': 'generated.tmp_files',
                        'output_dir': 'discover.tmp_dir'},
              provides={},
              kwargs={'limits': None}),
    StageSpec(cls=KustomizeBuild,
              requires={'kustomize_exec_dir': 'discover.kustomize_exec_dir',
                        'tmp_dir': 'discover.tmp_dir'},
              provides={'content': 'kustomize.content'},
              kwargs={'limits': None}),
    StageSpec(cls=SplitManifests,
              requires={'content': 'kustomize.content'},
              provides={'content': 'manifests.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'content': 'manifests.raw'},
              provides={'content': 'manifests.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'content': 'manifests.parsed'},
              provides={'files': 'generated.files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'files': 'generated.files',
                        'output_dir': 'discover.output_dir'},
              provides={},
              kwargs={'limits': None})
  ],
  PipelineType.K8S_HELMFILE: [
    StageSpec(cls=DiscoverK8sHelmfileApplication,
              requires={'viewer': 'source.viewer'},
              provides={'content': 'discover.content',
                        'template': 'discover.template',
                        'tmp_dir': 'discover.tmp_dir',
                        'output_dir': 'discover.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'template': 'discover.template'},
              provides={'content': 'template.content'}),
    StageSpec(cls=SplitManifests,
              requires={'content': 'discover.content&template.content'},
              provides={'content': 'staging.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'content': 'staging.raw'},
              provides={'content': 'staging.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'content': 'staging.parsed'},
              provides={'files': 'generated.tmp_files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'files': 'generated.tmp_files',
                        'output_dir': 'discover.tmp_dir'},
              provides={},
              kwargs={'limits': None}),
    StageSpec(cls=HelmfileRun,
              requires={'tmp_dir': 'discover.tmp_dir'},
              provides={'content': 'helmfile.content'},
              kwargs={'limits': None}),
    StageSpec(cls=SplitManifests,
              requires={'content': 'helmfile.content'},
              provides={'content': 'manifests.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'content': 'manifests.raw'},
              provides={'content': 'manifests.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'content': 'manifests.parsed'},
              provides={'files': 'generated.files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'files': 'generated.files',
                        'output_dir': 'discover.output_dir'},
              provides={},
              kwargs={'limits': None})
  ],
  PipelineType.K8S_APP_OF_APPS: [
    StageSpec(cls=DiscoverK8sAppOfAppsApplication,
              requires={},
              provides={'template': 'discover.template',
                        'output_dir': 'discover.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'template': 'discover.template'},
              provides={'content': 'template.content'}),
    StageSpec(cls=SplitManifests,
              requires={'content': 'template.content'},
              provides={'content': 'manifests.raw'}),
    StageSpec(cls=ConvertToYaml,
              requires={'content': 'manifests.raw'},
              provides={'content': 'manifests.parsed'}),
    StageSpec(cls=GenerateNames,
              requires={'content': 'manifests.parsed'},
              provides={'files': 'generated.files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'files': 'generated.files',
                        'output_dir': 'discover.output_dir'},
              provides={},
              kwargs={'limits': None}),
  ],
  PipelineType.GENERIC: [
    StageSpec(cls=DiscoverGenericApplication,
              requires={'viewer': 'source.viewer'},
              provides={'content': 'discover.content',
                        'template': 'discover.template',
                        'output_dir': 'discover.output_dir'}),
    StageSpec(cls=RenderTemplates,
              requires={'viewer': 'source.viewer',
                        'template': 'discover.template'},
              provides={'content': 'template.content'}),
    StageSpec(cls=GenerateNames,
              requires={'content': 'discover.content&template.content'},
              provides={'files': 'generated.files'},
              kwargs={'pipeline_kind': None}),
    StageSpec(cls=WriteOnDisk,
              requires={'files': 'generated.files',
                        'output_dir': 'discover.output_dir'},
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
  params = config.get_params(ctx.env_name, ctx.app_name)

  if params.app_type == ApplicationTypes.K8S:
    try:
      viewer = viewer.go_to(ctx.app_name)
      ctx_set(ctx, 'source.viewer', viewer)

      kustomize_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                                           name_pattern='kustomization|Kustomization',
                                                           depth=2))
      helmfile_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                                          name_pattern='helmfile',
                                                          depth=1))

      if kustomize_children:
        return _build_pipeline(PipelineType.K8S_KUSTOMIZE, limits)
      elif helmfile_children:
        return _build_pipeline(PipelineType.K8S_HELMFILE, limits)
      else:
        return _build_pipeline(PipelineType.K8S_SIMPLE, limits)
    except PathDoesNotExistError:
      return _build_pipeline(PipelineType.K8S_APP_OF_APPS, limits)
  elif params.app_type == ApplicationTypes.GENERIC:
    viewer = viewer.go_to(ctx.app_name)
    ctx_set(ctx, 'source.viewer', viewer)

    return _build_pipeline(PipelineType.GENERIC, limits)
  else:
    log.error(f'Unknown application type \'{params.app_type}\' in application {ctx.app_name} in environment {ctx.env_name}.'
              f' Valid types are: {[t.value for t in ApplicationTypes]}')
    raise ConfigFileError()

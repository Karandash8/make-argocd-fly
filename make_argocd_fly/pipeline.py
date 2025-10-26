import logging
import time
from enum import StrEnum, auto

from make_argocd_fly.context import Context, ctx_set
from make_argocd_fly.stage import Stage
from make_argocd_fly.config import get_config
from make_argocd_fly.param import ApplicationTypes
from make_argocd_fly.exception import ConfigFileError, PathDoesNotExistError
from make_argocd_fly.resource.viewer import ResourceType, ScopedViewer
from make_argocd_fly.stage import (DiscoverK8sSimpleApplication, DiscoverK8sKustomizeApplication, DiscoverK8sHelmfileApplication,
                                   DiscoverK8sAppOfAppsApplication, DiscoverGenericApplication, RenderTemplates, SplitManifests,
                                   GenerateManifestNames, GenerateOutputNames, WriteOnDisk, KustomizeBuild, HelmfileRun)
from make_argocd_fly.limits import RuntimeLimits


log = logging.getLogger(__name__)


class PipelineType(StrEnum):
  K8S_SIMPLE = auto()
  K8S_KUSTOMIZE = auto()
  K8S_HELMFILE = auto()
  K8S_APP_OF_APPS = auto()
  GENERIC = auto()


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


def build_pipeline_k8s_simple(limits: RuntimeLimits) -> Pipeline:
  stages = [DiscoverK8sSimpleApplication(),
            RenderTemplates(),
            SplitManifests(requires={'content': 'discover.content&template.content'}, provides={'content': 'manifest.content'}),
            GenerateManifestNames(requires={'content': 'manifest.content'}, provides={'files': 'output.files'}),
            WriteOnDisk(limits=limits, requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(PipelineType.K8S_SIMPLE, stages)


def build_pipeline_kustomize(limits: RuntimeLimits) -> Pipeline:
  stages = [DiscoverK8sKustomizeApplication(),
            RenderTemplates(),
            SplitManifests(requires={'content': 'discover.content&template.content'}, provides={'content': 'tmp_manifest.content'}),
            GenerateManifestNames(requires={'content': 'tmp_manifest.content'}, provides={'files': 'tmp_output.files'}),
            WriteOnDisk(limits=limits, requires={'files': 'tmp_output.files', 'output_dir': 'discover.tmp_dir'}),
            KustomizeBuild(limits=limits),
            SplitManifests(requires={'content': 'kustomize.content'}, provides={'content': 'manifest.content'}),
            GenerateManifestNames(requires={'content': 'manifest.content'}, provides={'files': 'output.files'}),
            WriteOnDisk(limits=limits, requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(PipelineType.K8S_KUSTOMIZE, stages)


def build_pipeline_helmfile(limits: RuntimeLimits) -> Pipeline:
  stages = [DiscoverK8sHelmfileApplication(),
            RenderTemplates(),
            SplitManifests(requires={'content': 'discover.content&template.content'}, provides={'content': 'tmp_manifest.content'}),
            GenerateManifestNames(requires={'content': 'tmp_manifest.content'}, provides={'files': 'tmp_output.files'}),
            WriteOnDisk(limits=limits, requires={'files': 'tmp_output.files', 'output_dir': 'discover.tmp_dir'}),
            HelmfileRun(limits=limits),
            SplitManifests(requires={'content': 'helmfile.content'}, provides={'content': 'manifest.content'}),
            GenerateManifestNames(requires={'content': 'manifest.content'}, provides={'files': 'output.files'}),
            WriteOnDisk(limits=limits, requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(PipelineType.K8S_HELMFILE, stages)


def build_pipeline_app_of_apps(limits: RuntimeLimits) -> Pipeline:
  stages = [DiscoverK8sAppOfAppsApplication(),
            RenderTemplates(),
            SplitManifests(requires={'content': 'template.content'}, provides={'content': 'manifest.content'}),
            GenerateManifestNames(requires={'content': 'manifest.content'}, provides={'files': 'output.files'}),
            WriteOnDisk(limits=limits, requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(PipelineType.K8S_APP_OF_APPS, stages)


def build_pipeline_generic(limits: RuntimeLimits) -> Pipeline:
  stages = [DiscoverGenericApplication(),
            RenderTemplates(),
            GenerateOutputNames(requires={'content': 'discover.content&template.content'}, provides={'files': 'output.files'}),
            WriteOnDisk(limits=limits, requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(PipelineType.GENERIC, stages)


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
        return build_pipeline_kustomize(limits)
      elif helmfile_children:
        return build_pipeline_helmfile(limits)
      else:
        return build_pipeline_k8s_simple(limits)
    except PathDoesNotExistError:
      return build_pipeline_app_of_apps(limits)
  elif params.app_type == ApplicationTypes.GENERIC:
    viewer = viewer.go_to(ctx.app_name)
    ctx_set(ctx, 'source.viewer', viewer)

    return build_pipeline_generic(limits)
  else:
    log.error(f'Unknown application type \'{params.app_type}\' in application {ctx.app_name} in environment {ctx.env_name}.'
              f' Valid types are: {[t.value for t in ApplicationTypes]}')
    raise ConfigFileError()

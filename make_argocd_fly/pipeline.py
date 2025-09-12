import logging
import time

from make_argocd_fly.context import Context, ctx_set
from make_argocd_fly.const import ApplicationType
from make_argocd_fly.stage import Stage
from make_argocd_fly.exception import ResourceViewerIsFake
from make_argocd_fly.resource.type import ResourceType
from make_argocd_fly.resource.viewer import ResourceViewer
from make_argocd_fly.stage import (DiscoverK8sSimpleApplication, DiscoverK8sKustomizeApplication, DiscoverK8sAppOfAppsApplication, RenderTemplates,
                                   SplitManifests, GenerateManifestNames, WriteYamls, KustomizeBuild)

log = logging.getLogger(__name__)


class Pipeline:
  def __init__(self, type: ApplicationType, stages: list[Stage]):
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


def build_pipeline_k8s_simple() -> Pipeline:
  stages = [DiscoverK8sSimpleApplication(),
            RenderTemplates(),
            SplitManifests(requires={'content': 'discover.content&template.content'}, provides={'content': 'manifest.content'}),
            GenerateManifestNames(requires={'content': 'manifest.content'}, provides={'files': 'output.files'}),
            WriteYamls(requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(ApplicationType.K8S_SIMPLE, stages)


def build_pipeline_k8s_kustomize() -> Pipeline:
  stages = [DiscoverK8sKustomizeApplication(),
            RenderTemplates(),
            SplitManifests(requires={'content': 'discover.content&template.content'}, provides={'content': 'tmp_manifest.content'}),
            GenerateManifestNames(requires={'content': 'tmp_manifest.content'}, provides={'files': 'tmp_output.files'}),
            WriteYamls(requires={'files': 'tmp_output.files', 'output_dir': 'discover.tmp_dir'}),
            KustomizeBuild(),
            SplitManifests(requires={'content': 'kustomize.content'}, provides={'content': 'manifest.content'}),
            GenerateManifestNames(requires={'content': 'manifest.content'}, provides={'files': 'output.files'}),
            WriteYamls(requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(ApplicationType.K8S_KUSTOMIZE, stages)


def build_pipeline_app_of_apps() -> Pipeline:
  stages = [DiscoverK8sAppOfAppsApplication(),
            RenderTemplates(),
            SplitManifests(requires={'content': 'template.content'}, provides={'content': 'manifest.content'}),
            GenerateManifestNames(requires={'content': 'manifest.content'}, provides={'files': 'output.files'}),
            WriteYamls(requires={'files': 'output.files', 'output_dir': 'discover.output_dir'})]

  return Pipeline(ApplicationType.K8S_APP_OF_APPS, stages)


def build_pipeline(ctx: Context, source_path: str) -> Pipeline:
  viewer = ResourceViewer(source_path)
  ctx_set(ctx, 'source.viewer', viewer)

  try:
    kustomize_children = list(viewer.search_subresources(resource_types=[ResourceType.YAML],
                                                         name_pattern='kustomization|Kustomization'))

    if kustomize_children:
      return build_pipeline_k8s_kustomize()
    else:
      return build_pipeline_k8s_simple()
  except ResourceViewerIsFake:
    return build_pipeline_app_of_apps()

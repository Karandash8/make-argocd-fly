import logging
import os
import yaml
import yaml.composer
import yaml.parser
import yaml.scanner
import yaml.constructor

try:
  from yaml import CSafeLoader as SafeLoader
except ImportError:
  from yaml import SafeLoader

from make_argocd_fly.context import Context, ctx_get, ctx_set, resolve_expr
from make_argocd_fly.context.data import Resource
from make_argocd_fly.resource.viewer import ResourceType
from make_argocd_fly.exception import (UndefinedTemplateVariableError, TemplateRenderingError, InternalError,
                                       PathDoesNotExistError, OutputFilenameConstructionError)
from make_argocd_fly.renderer import JinjaRenderer
from make_argocd_fly.util import extract_single_resource, get_app_rel_path, is_one_of
from make_argocd_fly.namegen import (K8sInfo, SourceInfo, K8sPolicy, SourcePolicy, Deduper, RoutingRules,
                                     KUSTOMIZE_BASENAMES, HELMFILE_BASENAMES)
from make_argocd_fly.type import PipelineType, NamingPolicyType, WriterType


log = logging.getLogger(__name__)


class RenderTemplates:
  name = 'RenderTemplates'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    templated_resources = ctx_get(ctx, self.requires['templated_resources'])
    viewer = ctx_get(ctx, self.requires['viewer'])

    renderer = JinjaRenderer()
    renderer.set_resource_viewer(viewer)
    out_resources = []

    for template in templated_resources:
      renderer.set_template_vars(template.vars)
      renderer.set_template_origin(template.origin)

      try:
        result = renderer.render(template.data)

        out_resources.append(Resource(resource_type=template.resource_type,
                                      data=result,
                                      origin=template.origin,
                                      source_path=template.source_path))
      except (UndefinedTemplateVariableError, PathDoesNotExistError, InternalError) as e:
        log.error(f'{e}')
        raise TemplateRenderingError(template.origin, ctx.app_name, ctx.env_name, f'Error rendering template {template.origin}') from e

    ctx_set(ctx, self.provides['resources'], out_resources)


class SplitManifests:
  name = 'SplitManifests'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    in_resources: list[Resource] = resolve_expr(ctx, self.requires['resources'])

    out_resources = []
    for resource in in_resources:
      if resource.resource_type == ResourceType.YAML:
        for single in extract_single_resource(resource.data):
          out_resources.append(Resource(resource_type=ResourceType.YAML,
                                        data=single,
                                        origin=resource.origin,
                                        source_path=resource.source_path))
      else:
        out_resources.append(resource)

    ctx_set(ctx, self.provides['resources'], out_resources)


class ConvertToYaml:
  name = 'ConvertToYaml'

  def __init__(self, requires: dict[str, str], provides: dict[str, str]) -> None:
    self.requires = requires
    self.provides = provides

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    in_resources: list[Resource] = resolve_expr(ctx, self.requires['resources'])
    out_resources: list[Resource] = []

    for resource in in_resources:
      if resource.resource_type == ResourceType.YAML:
        try:
          obj = yaml.load(resource.data, Loader=SafeLoader)
          out_resources.append(resource.with_yaml(obj))
        except (yaml.composer.ComposerError, yaml.parser.ParserError, yaml.scanner.ScannerError, yaml.constructor.ConstructorError):
          log.warning(f'YAML parse failed in ConvertToYaml for origin={resource.origin} path={resource.source_path}; leaving as text')
          out_resources.append(resource)
      else:
        out_resources.append(resource)

    ctx_set(ctx, self.provides['resources'], out_resources)


class GenerateNames:
  name = 'GenerateNames'

  def __init__(self, requires: dict[str, str],
               provides: dict[str, str],
               *,
               pipeline_kind: PipelineType) -> None:
    self.requires = requires
    self.provides = provides
    self.pipeline_kind = pipeline_kind
    self.k8s_policy = K8sPolicy()
    self.src_policy = SourcePolicy()

    if self.pipeline_kind is None:
      raise InternalError(f'PipelineType must be provided to `{self.name}` stage')

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} (pipeline_kind={self.pipeline_kind})')
    in_resources: list[Resource] = resolve_expr(ctx, self.requires['resources'])

    rules = RoutingRules(
      pipeline_kind=self.pipeline_kind,
      kustomize_cfg=set(resolve_expr(ctx, 'discovered.kustomize_config_files') or []),
      helmfile_cfg=set(resolve_expr(ctx, 'discovered.helmfile_config_files') or []),
    )

    app_rel = get_app_rel_path(ctx.env_name, ctx.app_name)
    dedupe = Deduper()
    out_resources: list[Resource] = []

    for res in sorted(in_resources, key=lambda r: (r.source_path or '', r.origin)):
      log.debug(f'Processing resource: origin={res.origin} path={res.source_path}')

      policy_key = self._route_policy(res, rules)
      src = SourceInfo.from_source_path(res.source_path)

      try:
        if policy_key == NamingPolicyType.K8S:
          k8s = K8sInfo.from_yaml_obj(res.yaml_obj)
          rel = self.k8s_policy.render(k8s=k8s, src=src)
        elif policy_key == NamingPolicyType.SOURCE:
          rel = self.src_policy.render(k8s=None, src=src)
        elif policy_key is None:
          log.warning(f'Skipping resource due to no naming policy found (origin={res.origin} path={res.source_path}) '
                      f'for application {ctx.app_name} in environment {ctx.env_name}')
          continue
        else:
          log.warning(f'Skipping resource due to unknown policy \'{policy_key}\' (origin={res.origin} path={res.source_path})'
                      f' for application {ctx.app_name} in environment {ctx.env_name}')
          continue
      except OutputFilenameConstructionError as e:
        log.warning(f'Failed to construct output filename (origin={res.origin} path={res.source_path})'
                    f' for application {ctx.app_name} in environment {ctx.env_name}: {e}')
        continue

      rel = dedupe.unique(rel)
      out_resources.append(res.with_output_path(os.path.join(app_rel, rel)))

    ctx_set(ctx, self.provides['resources'], out_resources)

  def _route_policy(self, res: Resource, rules: RoutingRules) -> str | None:
    # Generic pipeline: always name by source
    if rules.pipeline_kind == PipelineType.GENERIC:
      return NamingPolicyType.SOURCE if res.source_path is not None else None

    # K8s pipelines
    if rules.pipeline_kind == PipelineType.K8S_KUSTOMIZE:
      # SourcePolicy for kustomization and values files
      if res.source_path and (is_one_of(res.source_path, KUSTOMIZE_BASENAMES) or res.source_path in rules.kustomize_cfg):
        return NamingPolicyType.SOURCE
      return NamingPolicyType.K8S if res.writer_type == WriterType.K8S_YAML else NamingPolicyType.SOURCE

    if rules.pipeline_kind == PipelineType.K8S_HELMFILE:
      # SourcePolicy for helmfile
      if res.source_path and (is_one_of(res.source_path, HELMFILE_BASENAMES) or res.source_path in rules.helmfile_cfg):
        return NamingPolicyType.SOURCE
      return NamingPolicyType.K8S if res.writer_type == WriterType.K8S_YAML else NamingPolicyType.SOURCE

    if rules.pipeline_kind in (PipelineType.K8S_SIMPLE, PipelineType.K8S_APP_OF_APPS):
      return NamingPolicyType.K8S if res.writer_type == WriterType.K8S_YAML else None
    return None

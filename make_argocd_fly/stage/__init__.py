# Re-export everything so that existing imports like
#   from make_argocd_fly.stage import DiscoverK8sSimpleApplication
# continue to work without any changes.

from make_argocd_fly.stage._base import (
  Stage,
  print_vars_deprecated,
  _resolve_template_vars,
  _discover_resources,
  _discover_templated_resources,
  _discover_extra_resources,
  _discover_templated_extra_resources,
)

from make_argocd_fly.stage.discover import (
  DiscoverK8sSimpleApplication,
  DiscoverK8sKustomizeApplication,
  DiscoverK8sHelmfileApplication,
  DiscoverK8sAppOfAppsApplication,
  DiscoverGenericApplication,
)

from make_argocd_fly.stage.process import (
  RenderTemplates,
  SplitManifests,
  ConvertToYaml,
  GenerateNames,
)

from make_argocd_fly.stage.write import (
  WriteOnDisk,
  KustomizeBuild,
  HelmfileRun,
)

__all__ = [
  # Protocol
  'Stage',
  # Shared helpers (used by tests and external code)
  'print_vars_deprecated',
  '_resolve_template_vars',
  '_discover_resources',
  '_discover_templated_resources',
  '_discover_extra_resources',
  '_discover_templated_extra_resources',
  # Discover stages
  'DiscoverK8sSimpleApplication',
  'DiscoverK8sKustomizeApplication',
  'DiscoverK8sHelmfileApplication',
  'DiscoverK8sAppOfAppsApplication',
  'DiscoverGenericApplication',
  # Process stages
  'RenderTemplates',
  'SplitManifests',
  'ConvertToYaml',
  'GenerateNames',
  # Write stages
  'WriteOnDisk',
  'KustomizeBuild',
  'HelmfileRun',
]

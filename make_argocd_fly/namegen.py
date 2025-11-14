import os
import re
import logging
from typing import Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import PurePosixPath

from make_argocd_fly.type import PipelineType
from make_argocd_fly.exception import OutputFilenameConstructionError


log = logging.getLogger(__name__)

_normalize_re = re.compile(r'[^A-Za-z0-9._-]+')

KUSTOMIZE_BASENAMES = frozenset({
  'kustomization.yml',
  'kustomization.yaml',
  'kustomization.yml.j2',
  'kustomization.yaml.j2',
  'Kustomization.yml',
  'Kustomization.yaml',
  'Kustomization.yml.j2',
  'Kustomization.yaml.j2',
  'values.yml',
  'values.yaml',
  'values.yml.j2',
  'values.yaml.j2',
})

HELMFILE_BASENAMES = frozenset({
  'helmfile.yaml',
  'helmfile.yaml.j2',
})


@dataclass(frozen=True)
class RoutingRules:
  pipeline_kind: PipelineType
  kustomize_cfg: set[str]
  helmfile_cfg: set[str]


def _normalize(s: str | None) -> str | None:
  if not s:
    return s
  return _normalize_re.sub('-', s).strip('-').lower()


@dataclass(frozen=True)
class K8sInfo:
  api_version: str | None
  kind: str | None
  name: str | None
  namespace: str | None
  group: str | None
  version: str | None

  @staticmethod
  def from_yaml_obj(obj: Any) -> 'K8sInfo':
    if not isinstance(obj, dict):
      return K8sInfo(None, None, None, None, None, None)

    api = obj.get('apiVersion')
    kind = obj.get('kind')
    meta = obj.get('metadata') or {}
    name = meta.get('name')
    ns = meta.get('namespace')

    group = version = None
    if isinstance(api, str):
      parts = api.split('/', 1)
      if len(parts) == 2:
        group, version = parts
      else:
        version = parts[0]

    return K8sInfo(
      api_version=api if isinstance(api, str) else None,
      kind=kind if isinstance(kind, str) else None,
      name=name if isinstance(name, str) else None,
      namespace=ns if isinstance(ns, str) else None,
      group=group,
      version=version
    )


@dataclass(frozen=True)
class SourceInfo:
  rel_dir: str
  source_stem: str  # name without .j2 and extension
  source_ext: str   # includes leading dot or ''

  @staticmethod
  def from_source_path(source_rel: str) -> 'SourceInfo':
    p = PurePosixPath(source_rel)
    rel_dir = '.' if str(p.parent) == '.' else str(p.parent)
    base = p.name.removesuffix('.j2')
    if '.' in base:
      stem, ext = base.rsplit('.', 1)
      ext = '.' + ext

      if stem == '':
        stem = ext
        ext = ''
    else:
      stem, ext = base, ''

    return SourceInfo(rel_dir=rel_dir, source_stem=stem, source_ext=ext)


@dataclass
class Pattern:
  template: str  # e.g. '{rel_dir}/{kind}_{name}.yml'
  lower: bool = False

  def apply(self, fields: dict[str, str]) -> str:
    out = self.template.format(**fields)
    out = out.replace('//', '/').lstrip('/')

    if self.lower:
      out = out.lower()

    return os.path.normpath(out)


class NamePolicy(ABC):
  @abstractmethod
  def render(self, *, k8s: K8sInfo | None, src: SourceInfo) -> str:
    raise NotImplementedError()


class SourcePolicy(NamePolicy):
  def __init__(self, pattern: Pattern | None = None):
    self.pattern = pattern or Pattern('{rel_dir}/{source_stem}{source_ext}')

  def render(self, *, k8s: K8sInfo | None, src: SourceInfo) -> str:
    fields = {
      'rel_dir': src.rel_dir,
      'source_stem': src.source_stem,
      'source_ext': src.source_ext,
    }

    try:
      relpath = self.pattern.apply(fields)
    except KeyError as e:
      raise OutputFilenameConstructionError(e.args[0])

    return relpath


class K8sPolicy(NamePolicy):
  def __init__(self, pattern: Pattern | None = None):
    self.pattern = pattern or Pattern('{rel_dir}/{kind}_{name}.yml')

  def render(self, *, k8s: K8sInfo | None, src: SourceInfo) -> str:
    if not k8s:
      raise OutputFilenameConstructionError()

    fields = {
      'rel_dir': src.rel_dir,
      'source_stem': src.source_stem,
      'source_ext': src.source_ext,
    }
    if _kind := _normalize(k8s.kind):
      fields['kind'] = _kind
    if _name := _normalize(k8s.name):
      fields['name'] = _name
    if _namespace := _normalize(k8s.namespace):
      fields['namespace'] = _namespace
    if _api_version := _normalize(k8s.api_version):
      fields['api_version'] = _api_version
    if _group := _normalize(k8s.group):
      fields['group'] = _group
    if _version := _normalize(k8s.version):
      fields['version'] = _version

    try:
      relpath = self.pattern.apply(fields)
    except KeyError as e:
      raise OutputFilenameConstructionError(e.args[0])

    return relpath


class Deduper:
  def __init__(self) -> None:
    self._seen: set[str] = set()

  def unique(self, relpath: str) -> str:
    if relpath not in self._seen:
      self._seen.add(relpath)
      return relpath

    base, ext = os.path.splitext(relpath)
    i = 1
    while True:
      indexed = f'{base}_{i}{ext}'
      if indexed not in self._seen:
        self._seen.add(indexed)
        return indexed
      i += 1

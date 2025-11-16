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
  source_ext: str  # includes leading dot or ''

  @staticmethod
  def from_source_path(source_rel: str | None) -> 'SourceInfo | None':
    if source_rel is None:
      return None

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


def _normalize(s: str | None) -> str | None:
  if s is None:
    return s
  return _normalize_re.sub('-', s).strip('-').lower()


def _add_normalized(fields: dict[str, str], key: str, raw: str | None) -> None:
  '''Normalize value and add to fields if non-empty.'''
  norm = _normalize(raw)
  if norm:
    fields[key] = norm


class NamePolicy(ABC):
  @abstractmethod
  def render(self, *, k8s: K8sInfo | None, src: SourceInfo | None) -> str:
    raise NotImplementedError()


class SourcePolicy(NamePolicy):
  def __init__(self, pattern: Pattern | None = None):
    self.pattern = pattern or Pattern('{rel_dir}/{source_stem}{source_ext}')

  def render(self, *, k8s: K8sInfo | None, src: SourceInfo | None) -> str:
    if src is None:
      raise OutputFilenameConstructionError()

    fields: dict[str, str] = {
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

  def render(self, *, k8s: K8sInfo | None, src: SourceInfo | None) -> str:
    if not k8s:
      raise OutputFilenameConstructionError()

    rel_dir = src.rel_dir if src is not None else '.'
    fields: dict[str, str] = {'rel_dir': rel_dir}

    if src is not None:
      if src.source_stem is not None:
        fields['source_stem'] = src.source_stem
      if src.source_ext is not None:
        fields['source_ext'] = src.source_ext

    for key, raw in (('kind', k8s.kind),
                     ('name', k8s.name),
                     ('namespace', k8s.namespace),
                     ('api_version', k8s.api_version),
                     ('group', k8s.group),
                     ('version', k8s.version)):
      _add_normalized(fields, key, raw)

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

import logging
import os
import asyncio
from typing import Any

from make_argocd_fly.context import Context, ctx_get, ctx_set
from make_argocd_fly.context.data import Resource
from make_argocd_fly.resource.viewer import ResourceType
from make_argocd_fly.resource.writer import AbstractWriter, GENERIC_WRITER, YAML_WRITER
from make_argocd_fly.exception import InternalError, KustomizeError, HelmfileError
from make_argocd_fly.util import get_app_rel_path, remove_dir
from make_argocd_fly.limits import RuntimeLimits
from make_argocd_fly.type import WriterType


log = logging.getLogger(__name__)


class WriteOnDisk:
  name = 'WriteOnDisk'

  def __init__(self, requires: dict[str, str], provides: dict[str, str], *, limits: RuntimeLimits) -> None:
    self.requires = requires
    self.provides = provides
    self.limits = limits
    self._written = set()

    if self.limits is None:
      raise InternalError(f'RuntimeLimits must be provided to `{self.name}` stage')

  async def _write_one(self, writer: AbstractWriter, payload: Any, output_dir: str, ctx: Context, resource: Resource) -> None:
    async with self.limits.io_sem:
      path = os.path.join(output_dir, resource.output_path)
      if path in self._written:
        raise InternalError(f'Duplicate output: {path}')
      self._written.add(path)

      # Offload the blocking write to a thread, bounded by io_sem
      await asyncio.to_thread(writer.write, path, payload, ctx.env_name, ctx.app_name, resource.origin)

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    resources = ctx_get(ctx, self.requires['resources'])
    output_dir = ctx_get(ctx, self.requires['output_dir'])
    self._written = set()

    for resource in resources:
      if resource.output_path is None:
        raise InternalError(f'Resource `{resource.origin}` passed to `{self.name}` stage without output_path')

      # Disallow writing non-files
      if resource.resource_type in (ResourceType.DIRECTORY, ResourceType.DOES_NOT_EXIST):
        raise InternalError(f'Cannot write resource of type `{resource.resource_type.name}` (origin=`{resource.origin}`)')

    app_output_dir = os.path.join(output_dir, get_app_rel_path(ctx.env_name, ctx.app_name))
    remove_dir(app_output_dir)

    try:
      async with asyncio.TaskGroup() as tg:
        for resource in sorted(resources, key=lambda r: r.output_path):
          if resource.writer_type == WriterType.K8S_YAML:
            writer = YAML_WRITER
            payload = resource.yaml_obj
          else:
            writer = GENERIC_WRITER
            payload = resource.data

          tg.create_task(self._write_one(writer, payload, output_dir, ctx, resource))
    except ExceptionGroup as e:
      if e.exceptions:
        raise e.exceptions[0]
      else:
        raise e


class KustomizeBuild:
  name = 'KustomizeBuild'

  def __init__(self, requires: dict[str, str], provides: dict[str, str], *, limits: RuntimeLimits) -> None:
    self.requires = requires
    self.provides = provides
    self.limits = limits

    if self.limits is None:
      raise InternalError(f'RuntimeLimits must be provided to `{self.name}` stage')

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    kustomize_exec_dir = ctx_get(ctx, self.requires['kustomize_exec_dir'])
    tmp_dir = ctx_get(ctx, self.requires['tmp_dir'])

    dir_path = os.path.normpath(os.path.join(tmp_dir, get_app_rel_path(ctx.env_name, ctx.app_name), kustomize_exec_dir))
    retries = 3

    try:
      async with self.limits.subproc_sem:
        for attempt in range(retries):
          proc = await asyncio.create_subprocess_exec(
            'kustomize', 'build', '--enable-helm', '.',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=dir_path)

          stdout, stderr = await proc.communicate()
          if proc.returncode != 0:
            log.error(f'Kustomize error: {stderr.decode("utf-8", "ignore")}')

            delay = min(2 ** attempt, 4) + (attempt * 0.1)
            log.info(f'Retrying {attempt + 1}/{retries} after {delay:.1f}s')
            await asyncio.sleep(delay)
            continue
          break
        else:
          raise KustomizeError(ctx.app_name, ctx.env_name)
    except FileNotFoundError as e:
      raise KustomizeError(ctx.app_name, ctx.env_name, f'`{e.filename}` not found') from e

    resources = [Resource(resource_type=ResourceType.YAML,
                          data=stdout.decode('utf-8'),
                          origin='Kustomize',
                          source_path=None)]
    ctx_set(ctx, self.provides['resources'], resources)


class HelmfileRun:
  name = 'HelmfileRun'

  def __init__(self, requires: dict[str, str], provides: dict[str, str], *, limits: RuntimeLimits) -> None:
    self.requires = requires
    self.provides = provides
    self.limits = limits

    if self.limits is None:
      raise InternalError(f'RuntimeLimits must be provided to `{self.name}` stage')

  async def run(self, ctx: Context) -> None:
    log.debug(f'Run {self.name} stage')
    tmp_dir = ctx_get(ctx, self.requires['tmp_dir'])

    dir_path = os.path.join(tmp_dir, get_app_rel_path(ctx.env_name, ctx.app_name))
    retries = 3

    try:
      async with self.limits.subproc_sem:
        for attempt in range(retries):
          proc = await asyncio.create_subprocess_exec(
            'helmfile', 'template', '--quiet',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=dir_path)

          stdout, stderr = await proc.communicate()
          if proc.returncode != 0:
            log.error(f'Helmfile error: {stderr.decode("utf-8", "ignore")}')

            delay = min(2 ** attempt, 4) + (attempt * 0.1)
            log.info(f'Retrying {attempt + 1}/{retries} after {delay:.1f}s')
            await asyncio.sleep(delay)
            continue
          break
        else:
          raise HelmfileError(ctx.app_name, ctx.env_name)
    except FileNotFoundError as e:
      raise HelmfileError(ctx.app_name, ctx.env_name, f'`{e.filename}` not found') from e

    resources = [Resource(resource_type=ResourceType.YAML,
                          data=stdout.decode('utf-8'),
                          origin='Helmfile',
                          source_path=None)]
    ctx_set(ctx, self.provides['resources'], resources)

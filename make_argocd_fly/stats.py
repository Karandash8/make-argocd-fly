import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass

from make_argocd_fly.context import Context
from make_argocd_fly.pipeline import Pipeline
from make_argocd_fly.type import PipelineType

log = logging.getLogger(__name__)


@dataclass
class StageStats:
    samples: list[float]

    def add(self, ms: float) -> None:
        self.samples.append(ms)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples)

    @property
    def std(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) >= 2 else 0.0

    @property
    def minimum(self) -> float:
        return min(self.samples)

    @property
    def maximum(self) -> float:
        return max(self.samples)


def _collect(apps: list[tuple[Pipeline, Context]]):
  per_pipeline_stage_idx: dict[PipelineType, dict[tuple[int, str], StageStats]] = defaultdict(lambda: defaultdict(lambda: StageStats(samples=[])))
  per_app: list[tuple[PipelineType, str, str, float]] = []

  for pipeline, ctx in apps:
    total_ms = 0.0
    for entry in ctx.trace:
      stage_name = entry.get('stage', '?')
      idx = int(entry.get('index', -1))
      ms = float(entry.get('ms', 0.0) or 0.0)
      total_ms += ms

      key = (idx, stage_name)
      per_pipeline_stage_idx[pipeline.type][key].add(ms)

    per_app.append((pipeline.type, ctx.env_name, ctx.app_name, total_ms))

  return per_pipeline_stage_idx, per_app


def print_stats(apps: list[tuple[Pipeline, Context]], wall_ms: float | None = None) -> None:
  per_pipeline_stage_idx, per_app = _collect(apps)

  if not per_app:
    log.info('No applications rendered, no statistics to show')
    return

  log.info('--- Pipeline statistics ---')
  log.info(f'Total applications: {len(per_app)}')
  if wall_ms is not None:
    log.info(f'Wall-clock time for applications generation: {wall_ms:.1f} ms')

  # Top 10 slowest apps
  log.info('')
  log.info('Top 10 slowest applications:')
  for pipeline_type, env, app, t in sorted(per_app, key=lambda x: x[3], reverse=True)[:10]:
    log.info(f'  {pipeline_type.name:15} {env}/{app:30} {t:8.1f} ms')

  # Per-pipeline-type per-stage stats
  log.info('')
  log.info('Per-pipeline-type / per-stage summary:')
  for pipeline_type, stages in per_pipeline_stage_idx.items():
    log.info(f'  [{pipeline_type.name}] (apps: {len(stages[next(iter(stages))].samples)})')
    for (idx, stage_name), s in sorted(stages.items(), key=lambda kv: kv[0][0]):
      log.info(
        f'    #{idx:02d} {stage_name:35} '
        f'min={s.minimum:8.1f} ms  max={s.maximum:8.1f} ms  '
        f'mean={s.mean:8.1f} ms  std={s.std:8.1f} ms'
      )

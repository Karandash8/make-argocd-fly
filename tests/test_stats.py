import math
import logging

from make_argocd_fly.stats import StageStats, _collect, print_stats
from make_argocd_fly.context import Context
from make_argocd_fly.pipeline import Pipeline
from make_argocd_fly.type import PipelineType
from make_argocd_fly.param import Params


###################
### StageStats
###################

def test_StageStats__single_sample():
  stats = StageStats(samples=[])

  stats.add(42.0)

  assert stats.mean == 42.0
  assert stats.minimum == 42.0
  assert stats.maximum == 42.0
  # std is defined as 0.0 when there is a single sample
  assert stats.std == 0.0

def test_StageStats__multiple_samples():
  stats = StageStats(samples=[])

  for value in (1.0, 2.0, 3.0):
    stats.add(value)

  assert stats.mean == 2.0
  assert stats.minimum == 1.0
  assert stats.maximum == 3.0
  # Sample stdev of [1, 2, 3] is 1.0
  assert math.isclose(stats.std, 1.0)

###################
### _collect
###################

def _get_params() -> Params:
    return Params()

def test__collect__groups_by_pipeline_and_stage_index():
  # Two apps of the same pipeline type, with two stages each
  ctx1 = Context('env1', 'app1', _get_params())
  ctx1.trace.append({'stage': 'StageA', 'index': 0, 'ms': 10.0})
  ctx1.trace.append({'stage': 'StageB', 'index': 1, 'ms': 20.0})

  ctx2 = Context('env1', 'app2', _get_params())
  ctx2.trace.append({'stage': 'StageA', 'index': 0, 'ms': 40.0})
  ctx2.trace.append({'stage': 'StageB', 'index': 1, 'ms': 80.0})

  pipeline = Pipeline(PipelineType.K8S_SIMPLE, stages=[])
  apps = [(pipeline, ctx1), (pipeline, ctx2)]

  per_pipeline_stage_idx, per_app = _collect(apps)

  # per_app should have one entry per application with total time
  assert len(per_app) == 2
  assert per_app[0] == (PipelineType.K8S_SIMPLE, 'env1', 'app1', 30.0)
  assert per_app[1] == (PipelineType.K8S_SIMPLE, 'env1', 'app2', 120.0)

  # per_pipeline_stage_idx should group by (index, stage_name)
  assert PipelineType.K8S_SIMPLE in per_pipeline_stage_idx
  stages = per_pipeline_stage_idx[PipelineType.K8S_SIMPLE]

  assert (0, 'StageA') in stages
  assert (1, 'StageB') in stages

  s_a = stages[(0, 'StageA')]
  s_b = stages[(1, 'StageB')]

  assert sorted(s_a.samples) == [10.0, 40.0]
  assert s_a.minimum == 10.0
  assert s_a.maximum == 40.0

  assert sorted(s_b.samples) == [20.0, 80.0]
  assert s_b.minimum == 20.0
  assert s_b.maximum == 80.0

###################
### print_stats
###################

def test_print_stats__no_apps_logs_message(caplog):
  caplog.set_level(logging.INFO)

  print_stats([], wall_ms=123.4)

  assert 'No applications rendered, no statistics to show' in caplog.text

def test_print_stats__logs_summary_and_stage_lines(caplog):
  caplog.set_level(logging.INFO)

  ctx = Context('env1', 'app1', _get_params())
  # single stage, deterministic timing
  ctx.trace.append({'stage': 'MyStage', 'index': 0, 'ms': 50.0})

  pipeline = Pipeline(PipelineType.K8S_SIMPLE, stages=[])
  apps = [(pipeline, ctx)]

  print_stats(apps, wall_ms=123.4)

  text = caplog.text

  # High-level summary
  assert '--- Pipeline statistics ---' in text
  assert 'Total applications: 1' in text
  assert 'Wall-clock time for applications generation: 123.4 ms' in text

  # Top slowest applications section
  assert 'Top 10 slowest applications:' in text
  assert 'K8S_SIMPLE' in text
  assert 'env1/app1' in text
  assert '  K8S_SIMPLE' in text or '[K8S_SIMPLE]' in text

  # Per-pipeline-type per-stage summary
  # apps: 1 and a single stage line with min=max=mean=50.0, std=0.0
  assert '[K8S_SIMPLE] (apps: 1)' in text
  assert '#00 MyStage' in text
  assert 'min=    50.0 ms' in text
  assert 'max=    50.0 ms' in text
  assert 'mean=    50.0 ms' in text
  assert 'std=     0.0 ms' in text

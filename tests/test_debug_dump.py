import os
import json
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from make_argocd_fly import default
from make_argocd_fly.context import Context, ctx_set
from make_argocd_fly.debug_dump import _serialize_debug, StageContextDumper
from make_argocd_fly.param import Params


###################
### _serialize_debug
###################

@dataclass
class _DummyDC:
  x: int
  y: list[int]

def test__serialize_debug__primitives_and_collections():
  assert _serialize_debug(None) is None
  assert _serialize_debug(True) is True
  assert _serialize_debug(42) == 42
  assert _serialize_debug(3.14) == 3.14
  assert _serialize_debug('foo') == 'foo'

  assert _serialize_debug([1, 2]) == [1, 2]
  assert _serialize_debug((1, 2)) == [1, 2]   # tuple -> list
  assert _serialize_debug({1, 2}) == [1, 2] or _serialize_debug({1, 2}) == [2, 1]

  out = _serialize_debug({'a': 1, 'b': {'c': 2}})
  assert out == {'a': 1, 'b': {'c': 2}}

def test__serialize_debug__dataclass_and_fallback():
  dc = _DummyDC(x=1, y=[2, 3])
  assert _serialize_debug(dc) == {'x': 1, 'y': [2, 3]}

  class _Obj:
    pass

  obj = _Obj()
  out = _serialize_debug(obj)
  # Fallback should be a string repr
  assert isinstance(out, str)
  assert '_Obj' in out

###################
### StageContextDumper helpers
###################

class _DummyStage:
  def __init__(self, name='DummyStage', requires=None, provides=None):
    self.name = name
    self.requires = requires or {}
    self.provides = provides or {}

  async def run(self, ctx: Context) -> None: ...

def _patch_get_config(tmp_path, mocker):
  mock_get_config = MagicMock()
  mock_config = MagicMock()
  mock_config.tmp_dir = str(tmp_path)
  mock_get_config.return_value = mock_config
  mocker.patch('make_argocd_fly.debug_dump.get_config', mock_get_config)
  return mock_config

###################
### StageContextDumper.enabled == False
###################

def _get_params() -> Params:
    return Params()

def test_StageContextDumper__disabled_is_noop():
  ctx = Context('env', 'app', _get_params())
  dumper = StageContextDumper(enabled=False, ctx=ctx)

  # dump_root should not be initialised
  assert dumper.dump_root is None

  stage = _DummyStage()
  # These should not raise and should not touch filesystem / config
  dumper.dump_success(ctx, stage)
  dumper.dump_error(ctx, stage, RuntimeError('boom'))

###################
### dump_success
###################

def test_StageContextDumper__dump_success_writes_json(tmp_path, mocker):
  _patch_get_config(tmp_path, mocker)

  env_name = 'env1'
  app_name = 'app1'
  ctx = Context(env_name, app_name, _get_params())
  # Simulate that one stage already ran and updated trace
  ctx.trace.append({'stage': 'Prev', 'ms': 1.23})

  # Prepare input/output values in context
  ctx_set(ctx, 'in_ns.foo', {'k': 'v'})
  ctx_set(ctx, 'out_ns.bar', [1, 2, 3])

  stage = _DummyStage(
    name='MyStage',
    requires={'foo': 'in_ns.foo'},
    provides={'bar': 'out_ns.bar'},
  )

  dumper = StageContextDumper(enabled=True, ctx=ctx)
  dumper.dump_success(ctx, stage)

  dump_root = tmp_path / default.CONTEXT_DUMPS_DIR / env_name / app_name
  files = list(dump_root.iterdir())
  assert len(files) == 1

  # len(ctx.trace) == 1 -> "01_MyStage.json"
  assert files[0].name == '01_MyStage.json'

  payload = json.loads(files[0].read_text(encoding='utf-8'))

  assert payload['env_name'] == env_name
  assert payload['app_name'] == app_name
  assert payload['stage'] == 'MyStage'
  assert payload['trace_entry'] == ctx.trace[-1]

  # Inputs and outputs should be serialized structures
  assert payload['requires'] == {'foo': {'k': 'v'}}
  assert payload['provides'] == {'bar': [1, 2, 3]}

def test_StageContextDumper__dump_success_handles_resolve_and_ctx_get_errors(tmp_path, mocker, caplog):
  _patch_get_config(tmp_path, mocker)

  env_name = 'env'
  app_name = 'app'
  ctx = Context(env_name, app_name, _get_params())
  ctx.trace.append({'stage': 'S', 'ms': 10.0})

  stage = _DummyStage(
    name='ErrStage',
    requires={'foo': 'ns_in.foo'},
    provides={'bar': 'ns_out.bar'},
  )

  # Force resolve_expr and ctx_get to fail to exercise error branches
  mocker.patch('make_argocd_fly.debug_dump.resolve_expr', side_effect=Exception('boom_resolve'))
  mocker.patch('make_argocd_fly.debug_dump.ctx_get', side_effect=Exception('boom_get'))

  dumper = StageContextDumper(enabled=True, ctx=ctx)
  dumper.dump_success(ctx, stage)

  dump_root = tmp_path / default.CONTEXT_DUMPS_DIR / env_name / app_name
  files = list(dump_root.iterdir())
  assert len(files) == 1
  assert files[0].name == '01_ErrStage.json'

  payload = json.loads(files[0].read_text(encoding='utf-8'))

  # Errors should be rendered into string markers, not raised
  req = payload['requires']['foo']
  prov = payload['provides']['bar']

  assert req.startswith('<ERROR resolving ns_in.foo:')
  assert 'boom_resolve' in req

  assert prov.startswith('<MISSING ns_out.bar:')
  assert 'boom_get' in prov

def test_StageContextDumper__dump_success_file_write_failure_is_logged_not_raised(tmp_path, mocker, caplog):
  _patch_get_config(tmp_path, mocker)

  env_name = 'env'
  app_name = 'app'
  ctx = Context(env_name, app_name, _get_params())
  ctx.trace.append({'stage': 'S', 'ms': 5.0})

  ctx_set(ctx, 'in_ns.value', 1)
  ctx_set(ctx, 'out_ns.value', 2)

  stage = _DummyStage(
    name='LogStage',
    requires={'value': 'in_ns.value'},
    provides={'value': 'out_ns.value'},
  )

  dumper = StageContextDumper(enabled=True, ctx=ctx)

  # Force open() inside debug_dump to fail
  def _boom(*args, **kwargs):
    raise OSError('no disk')

  mocker.patch('make_argocd_fly.debug_dump.open', side_effect=_boom)

  # Should not raise, only log
  dumper.dump_success(ctx, stage)

  assert 'Failed to write debug dump' in caplog.text

###################
### dump_error
###################

def test_StageContextDumper__dump_error_writes_json(tmp_path, mocker):
  _patch_get_config(tmp_path, mocker)

  env_name = 'env'
  app_name = 'app'
  ctx = Context(env_name, app_name, _get_params())
  # No trace entries yet -> index 00
  assert len(ctx.trace) == 0

  ctx_set(ctx, 'in_ns.value', 123)

  stage = _DummyStage(
    name='FailStage',
    requires={'value': 'in_ns.value'},
    provides={},
  )

  dumper = StageContextDumper(enabled=True, ctx=ctx)
  exc = RuntimeError('boom')
  dumper.dump_error(ctx, stage, exc)

  dump_root = tmp_path / default.CONTEXT_DUMPS_DIR / env_name / app_name
  files = list(dump_root.iterdir())
  assert len(files) == 1
  assert files[0].name == '00_FailStage_error.json'

  payload = json.loads(files[0].read_text(encoding='utf-8'))

  assert payload['env_name'] == env_name
  assert payload['app_name'] == app_name
  assert payload['stage'] == 'FailStage'
  assert payload['error'] == repr(exc)
  assert payload['requires'] == {'value': 123}

def test_StageContextDumper__dump_error_file_write_failure_is_logged_not_raised(tmp_path, mocker, caplog):
  _patch_get_config(tmp_path, mocker)

  env_name = 'env'
  app_name = 'app'
  ctx = Context(env_name, app_name, _get_params())
  ctx.trace.append({'stage': 'S', 'ms': 5.0})

  ctx_set(ctx, 'in_ns.value', 1)
  ctx_set(ctx, 'out_ns.value', 2)

  stage = _DummyStage(
    name='LogStage',
    requires={'value': 'in_ns.value'},
    provides={'value': 'out_ns.value'},
  )

  dumper = StageContextDumper(enabled=True, ctx=ctx)

  # Force open() inside debug_dump to fail
  def _boom(*args, **kwargs):
    raise OSError('no disk')

  mocker.patch('make_argocd_fly.debug_dump.open', side_effect=_boom)

  # Should not raise, only log
  dumper.dump_error(ctx, stage, RuntimeError('boom'))

  assert 'Failed to write error debug dump' in caplog.text

import os
import json
import logging
from dataclasses import is_dataclass, asdict
from typing import Any

from make_argocd_fly.context import Context, ctx_get, resolve_expr
from make_argocd_fly.stage import Stage
from make_argocd_fly import default
from make_argocd_fly.config import get_config

log = logging.getLogger(__name__)


def _serialize_debug(value: Any) -> Any:
  if value is None or isinstance(value, (bool, int, float, str)):
    return value
  if isinstance(value, (list, tuple, set)):
    return [_serialize_debug(v) for v in value]
  if isinstance(value, dict):
    return {str(k): _serialize_debug(v) for k, v in value.items()}
  if is_dataclass(value):
    return _serialize_debug(asdict(value))
  return repr(value)


class StageContextDumper:
  def __init__(self, enabled: bool, ctx: Context):
    self.enabled = enabled
    if not enabled:
      self.dump_root = None
      return

    config = get_config()
    self.dump_root = os.path.join(
      config.tmp_dir,
      default.CONTEXT_DUMPS_DIR,
      ctx.env_name,
      ctx.app_name,
    )

  def _ensure_dir(self) -> None:
    if self.dump_root:
      os.makedirs(self.dump_root, exist_ok=True)

  def _capture_inputs(self, ctx: Context, stage: Stage) -> dict[str, object]:
    inputs: dict[str, object] = {}
    for name, expr in stage.requires.items():
      try:
        val = resolve_expr(ctx, expr)
      except Exception as e:
        val = f'<ERROR resolving {expr}: {e}>'
      inputs[name] = _serialize_debug(val)

    return inputs

  def _capture_outputs(self, ctx: Context, stage: Stage) -> dict[str, object]:
    outputs: dict[str, object] = {}
    for name, key in stage.provides.items():
      try:
        val = ctx_get(ctx, key)
      except Exception as e:
        val = f'<MISSING {key}: {e}>'
      outputs[name] = _serialize_debug(val)

    return outputs

  def dump_success(self, ctx: Context, stage: Stage) -> None:
    if not self.enabled:
      return

    self._ensure_dir()

    trace_entry = ctx.trace[-1] if ctx.trace else None
    filename = f'{len(ctx.trace):02d}_{stage.name}.json'
    path = os.path.join(self.dump_root, filename)
    inputs = self._capture_inputs(ctx, stage)
    outputs = self._capture_outputs(ctx, stage)

    payload = {
      'env_name': ctx.env_name,
      'app_name': ctx.app_name,
      'stage': stage.name,
      'trace_entry': trace_entry,
      'requires': inputs,
      'provides': outputs,
    }

    try:
      with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    except Exception as e:
      log.error(f'Failed to write debug dump {path}: {e!r}')

  def dump_error(self, ctx: Context, stage: Stage, exc: Exception) -> None:
    if not self.enabled:
      return

    self._ensure_dir()

    filename = f'{len(ctx.trace):02d}_{stage.name}_error.json'
    path = os.path.join(self.dump_root, filename)
    inputs = self._capture_inputs(ctx, stage)

    payload = {
      'env_name': ctx.env_name,
      'app_name': ctx.app_name,
      'stage': stage.name,
      'error': repr(exc),
      'requires': inputs,
    }

    try:
      with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    except Exception as e:
      log.error(f'Failed to write error debug dump {path}: {e!r}')

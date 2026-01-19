import logging
from dataclasses import dataclass, field
from typing import Any

from make_argocd_fly.param import Params


log = logging.getLogger(__name__)


@dataclass
class NS:
  data: dict[str, Any] = field(default_factory=dict)


class Context:
  def __init__(self, env_name: str, app_name: str, params: Params):
    self.env_name = env_name
    self.app_name = app_name
    self.params = params
    self.trace: list[dict] = []
    self._ns: dict[str, NS] = {}

  def ns(self, name: str) -> NS:
    ns = self._ns.get(name)
    if ns is None:
      ns = self._ns[name] = NS()
    return ns


# TODO: make the following functions methods of Context?
# TODO: deal with dotted keys in a more robust way. Check that there is something to split.
def ctx_get(ctx: Context, dotted: str) -> Any:
  ns, key = dotted.split(".", 1)
  ns_obj = ctx._ns.get(ns)
  return None if ns_obj is None else ns_obj.data.get(key)


def ctx_set(ctx: Context, dotted: str, value: Any) -> None:
  ns, key = dotted.split(".", 1)
  ctx.ns(ns).data[key] = value


def merge_values(vals: Any) -> Any:
  vals = [v for v in vals if v is not None]
  if not vals:
    return None
  if all(isinstance(v, list) for v in vals):
    out = []
    for v in vals:
      out.extend(v)
    return out
  if all(isinstance(v, dict) for v in vals):
    out = {}
    for v in vals:
      out.update(v)
    return out
  return vals


def resolve_expr(ctx: Context, expr: str) -> Any:
  expr = expr.strip()
  if "&" in expr:
    parts = [p.strip() for p in expr.split("&")]
    return merge_values([ctx_get(ctx, p) for p in parts])
  if "|" in expr:
    for p in [q.strip() for q in expr.split("|")]:
      v = ctx_get(ctx, p)
      if v is not None:
        return v
    return None
  return ctx_get(ctx, expr)

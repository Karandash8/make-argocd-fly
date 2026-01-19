import pytest
from make_argocd_fly.context import NS, Context, ctx_get, ctx_set
from make_argocd_fly.param import Params


def _get_params() -> Params:
    return Params()

##################
### Context
##################

def test_Context__ns() -> None:
    ctx = Context("test_env", "test_app", _get_params())
    ns = ctx.ns("test_ns")

    assert ctx.env_name == "test_env"
    assert ctx.app_name == "test_app"
    assert ns == ctx.ns("test_ns")

##################
### ctx_get
##################

def test_ctx__get() -> None:
    ctx = Context("test_env", "test_app", _get_params())
    ns = ctx.ns("test_ns")
    ns.data["key"] = "value"

    assert ctx_get(ctx, "test_ns.key") == "value"
    assert ctx_get(ctx, "non_existent_ns.key") is None
    assert ctx_get(ctx, "test_ns.non_existent_key") is None

##################
### ctx_set
##################

def test_ctx__set() -> None:
    ctx = Context("test_env", "test_app", _get_params())

    ctx_set(ctx, "test_ns.key", "value")
    ns = ctx.ns("test_ns")

    assert ns.data["key"] == "value"

    ctx_set(ctx, "test_ns.another_key", "another_value")
    assert ns.data["another_key"] == "another_value"

    ctx_set(ctx, "new_ns.new_key", "new_value")
    new_ns = ctx.ns("new_ns")
    assert new_ns.data["new_key"] == "new_value"

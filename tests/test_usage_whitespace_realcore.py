"""Real-core whitespace and snapshot-route regressions from review 6093720310.

Effects are recording/raising doubles; no OAuth, HTTP or credential-store access.
The SQL-denying runner installs its guard before collecting this module.
"""
import asyncio
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import pytest

core = pytest.importorskip("agent.account_usage")
from dashboard import plugin_api


def _run(fn):
    calls = []

    def denied(name):
        def forbidden(*args, **kwargs):
            calls.append((name, kwargs))
            raise AssertionError(f"{name} denied")
        return forbidden

    with ExitStack() as stack:
        for name in ("resolve_codex_runtime_credentials", "resolve_anthropic_token", "resolve_runtime_provider", "_get_json"):
            stack.enter_context(patch.object(core, name, denied(name)))
        stack.enter_context(patch.dict("sys.modules", {"agent.credential_pool": SimpleNamespace(
            load_pool=denied("load_pool"), _codex_principal_identity=lambda token: None)}))
        result = fn()
    return result, calls


@pytest.mark.parametrize("token", ["   ", "\t", "\n", "\u2003"])
@pytest.mark.parametrize("provider", ["openai-codex", "openrouter", "anthropic", "xai-oauth"])
def test_whitespace_token_never_reaches_core_effects(provider, token):
    result, calls = _run(lambda: plugin_api._fetch_account_usage(provider, token))
    assert calls == []
    assert result is None


@pytest.mark.parametrize("provider", ["openai-codex", "openrouter"])
def test_whitespace_snapshot_row_never_reaches_ambient_discovery(provider):
    snap = plugin_api._snapshot_from_row(provider, {"id": "ws", "label": "x", "access_token": "  ", "priority": 0})

    async def collect():
        return await plugin_api._collect_usage_from_snapshots(provider, [snap], "Quota", None, True)

    _, calls = _run(lambda: asyncio.run(collect()))
    assert calls == []


def test_control_real_token_codex_reaches_only_http():
    result, calls = _run(lambda: plugin_api._fetch_account_usage("openai-codex", "fixture-explicit-token"))
    assert result is None
    assert [c[0] for c in calls] == ["_get_json"]

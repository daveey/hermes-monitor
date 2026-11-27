"""Real core dispatch with denied credential seams, not a live OAuth/HTTP proof.

The no-SQL runner installs its connection denial before collecting this module.
Without an installed core this module is explicitly skipped, not simulated.
"""
import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

core = pytest.importorskip("agent.account_usage")
httpx = pytest.importorskip("httpx")
from dashboard import plugin_api


def test_no_token_never_reaches_real_core_resolvers():
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("credential-effect")
        raise AssertionError("credential effect denied")

    with patch.object(core, "resolve_codex_runtime_credentials", forbidden), patch.object(
        core, "resolve_anthropic_token", forbidden
    ), patch.dict("sys.modules", {"agent.credential_pool": SimpleNamespace(load_pool=forbidden)}):
        for provider in ("openai-codex", "anthropic"):
            assert plugin_api._fetch_account_usage(provider) is None
            assert plugin_api._fetch_account_usage(provider, "") is None
    assert calls == []


def test_codex_401_does_not_refresh_but_default_core_control_does():
    calls = []

    def unauthorized(*args, **kwargs):
        request = httpx.Request("GET", "https://example.invalid/usage")
        raise httpx.HTTPStatusError("401", request=request, response=httpx.Response(401, request=request))

    def forbidden(*args, **kwargs):
        calls.append("load_pool")
        raise AssertionError("credential effect denied")

    with patch.object(core, "_get_json", unauthorized), patch.dict(
        "sys.modules", {"agent.credential_pool": SimpleNamespace(load_pool=forbidden)}
    ), patch.object(core, "_read_codex_tokens", return_value={"tokens": {"access_token": "other"}}):
        assert plugin_api._fetch_account_usage("openai-codex", "fixture-explicit-token") is None
        assert calls == []
        # A discriminating control: omission of read_only enters the denied pool.
        assert core.fetch_account_usage("openai-codex", api_key="fixture-explicit-token") is None
    assert calls == ["load_pool"]


def test_anthropic_real_clone_keeps_ambient_resolver_unreachable():
    calls, seen = [], []

    def forbidden(*args, **kwargs):
        calls.append("ambient-resolver")
        raise AssertionError("credential effect denied")

    def response(url, headers, *, timeout):
        seen.append(headers["Authorization"])
        return {"five_hour": {"utilization": 0.5, "resets_at": None}}

    token = "sk-ant-oat01-fixture-not-a-real-credential"
    with patch.object(core, "_get_json", response), patch.object(core, "resolve_anthropic_token", forbidden):
        result = plugin_api._fetch_account_usage("anthropic", token)
    assert calls == []
    assert seen == [f"Bearer {token}"]
    assert result is not None and result.windows

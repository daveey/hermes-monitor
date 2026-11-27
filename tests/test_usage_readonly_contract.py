"""Exercise the production poller boundary without SQL, network or credentials."""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dashboard import plugin_api


@pytest.mark.parametrize("provider", ["openai-codex", "xai-oauth", "openrouter", "anthropic"])
@pytest.mark.parametrize("token", [None, "fixture-access-token"])
def test_poller_explicitly_selects_core_read_only_fetcher(provider, token):
    calls = []
    mutations = []

    def fetch(slug, api_key=None, *, read_only=False):
        calls.append((slug, api_key, read_only))
        # Model the core's refresh-capable default; no actual credential writer.
        if not read_only:
            mutations.append("refresh-capable-path")
        return {"status": "unauthorized", "read_only": read_only}

    core = SimpleNamespace(fetch_account_usage=fetch)
    with patch.object(plugin_api.importlib, "import_module", return_value=core):
        result = plugin_api._fetch_account_usage(provider, token)
    assert calls == ([(provider, token, True)] if token else [])
    assert mutations == []
    assert result == ({"status": "unauthorized", "read_only": True} if token else None)


@pytest.mark.parametrize("provider", ["openai-codex", "xai-oauth", "openrouter", "anthropic"])
@pytest.mark.parametrize("token", [None, ""])
def test_missing_explicit_token_never_imports_core_or_loads_pool(provider, token):
    with patch.object(plugin_api.importlib, "import_module", side_effect=AssertionError("credential discovery forbidden")) as imports:
        assert plugin_api._fetch_account_usage(provider, token) is None
    imports.assert_not_called()


def test_async_core_fetch_preserves_read_only_keyword():
    calls = []

    async def fetch(provider, api_key=None, *, read_only=False):
        calls.append(read_only)
        return "quota"

    with patch.object(plugin_api.importlib, "import_module", return_value=SimpleNamespace(fetch_account_usage=fetch)):
        assert plugin_api._fetch_account_usage("openai-codex", "fixture-token") == "quota"
    assert calls == [True]


def test_legacy_core_without_read_only_support_never_retries_mutating_default():
    calls = []

    def fetch(provider, api_key=None):
        calls.append(provider)
        return "mutating-default"

    with patch.object(plugin_api.importlib, "import_module", return_value=SimpleNamespace(fetch_account_usage=fetch)):
        with pytest.raises(TypeError, match="read_only"):
            plugin_api._fetch_account_usage("openai-codex", "fixture-token")
    assert calls == []

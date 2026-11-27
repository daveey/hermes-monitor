"""Run the quota regression cohort with SQLite connection creation forbidden.

The repository's SQLite/credential-store integration tests are deliberately
not this cohort. Run the normal full suite separately where those are allowed.
"""
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def no_database(*args, **kwargs):
    raise AssertionError("read-only quota cohort must not open SQLite connections")


sqlite3.connect = no_database

import pytest

raise SystemExit(pytest.main([
    "tests/test_plugin_api.py", "tests/test_usage_readonly_contract.py", "tests/test_usage_realcore.py",
    "tests/test_quotas.py", "tests/test_workers.py", "-q", "-k",
    "not sqlite_connections and not worker_tool_events and not named_profile_quota and not sibling_quota "
    "and not load_running_tasks_uses_current_run_and_events",
]))

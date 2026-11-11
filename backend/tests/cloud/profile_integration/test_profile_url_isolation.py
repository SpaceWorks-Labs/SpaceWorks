"""Local-only Django checks for the eventual combined verification tree.

Run using the isolated backend harness; never evaluated in this lane's host Python.
"""

import ast
from pathlib import Path

from django.test import override_settings
from django.urls import Resolver404, resolve
import pytest

from config.cloud_settings.urls import free_tick_paths


@pytest.mark.parametrize("secret", ["", "set-but-inert"])
def test_full_tick_url_is_unresolved_for_every_method(secret):
    # URL resolution is method-independent: a mounted method-denying view is not
    # sufficient. These settings must produce NO pattern at all.
    with override_settings(SPACEWORKS_DEPLOYMENT_PROFILE="full", FREE_TICK_SECRET=secret):
        assert free_tick_paths("full") == []
        with pytest.raises(Resolver404):
            resolve("/api/v1/internal/free/tick")


def test_current_free_env_reads_have_explicit_backup_policy():
    from apps.backup.settings_policy import ENV_SURFACE, POLICIES, Policy

    source = Path(__file__).resolve().parents[3] / "config/settings.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and node.args[0].value.startswith("FREE_")
    }
    assert names == {
        "FREE_TICK_SECRET", "FREE_TICK_INTERVAL_SECONDS", "FREE_TICK_BUDGET_SECONDS",
        "FREE_TICK_RATE_LIMIT_PER_MINUTE", "FREE_DB_CAP_BYTES",
        "FREE_OBJECT_CAP_BYTES", "FREE_EMAIL_DAILY_CAP",
    }
    assert names <= ENV_SURFACE
    assert POLICIES["FREE_TICK_SECRET"].secret_bearing
    assert all(POLICIES[name].policy == Policy.EXCLUDED for name in names)

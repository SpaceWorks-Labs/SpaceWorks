import json

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.backup.host_marker import DatabaseIdentity, MarkerState, marker_payload
from apps.backup.host_readiness import HostReadinessError, assert_host_ready
from apps.backup.models import DeploymentRecoveryState


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _allow_unprivileged_temp_markers(monkeypatch):
    from apps.backup.host_marker import read_marker

    monkeypatch.setattr(
        "apps.backup.host_readiness.read_marker",
        lambda path: read_marker(path, require_root_owned=False),
    )


def _identity():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), oid FROM pg_database WHERE datname = current_database()")
        return DatabaseIdentity(*cursor.fetchone())


def _marker(path, *, identity=None, state=MarkerState.NORMAL):
    path.write_text(
        json.dumps(marker_payload(state, identity or _identity())),
        encoding="utf-8",
    )


def test_readiness_fails_when_live_database_oid_disagrees(tmp_path):
    marker = tmp_path / "marker.json"
    identity = _identity()
    _marker(marker, identity=DatabaseIdentity(identity.name, identity.oid + 1))

    with pytest.raises(HostReadinessError, match="identity"):
        assert_host_ready(marker)


def test_readiness_fails_when_marker_state_is_unknown(tmp_path):
    marker = tmp_path / "marker.json"
    payload = marker_payload(MarkerState.NORMAL, _identity())
    payload["state"] = "unknown-state"
    marker.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HostReadinessError, match="state"):
        assert_host_ready(marker)


def test_readiness_fails_when_marker_state_does_not_admit_backend(tmp_path):
    marker = tmp_path / "marker.json"
    _marker(marker, state=MarkerState.CANDIDATE_PREPARATION)

    with pytest.raises(HostReadinessError, match="does not admit"):
        assert_host_ready(marker)


def test_readiness_fails_when_migrations_disagree(tmp_path, monkeypatch):
    marker = tmp_path / "marker.json"
    _marker(marker)

    class PendingExecutor:
        def __init__(self, _connection):
            self.loader = type("Loader", (), {"graph": type("Graph", (), {
                "leaf_nodes": lambda self: [("backup", "9999_pending")]
            })()})()

        def migration_plan(self, _leaves):
            return [("backup", "9999_pending")]

    monkeypatch.setattr("apps.backup.host_readiness.MigrationExecutor", PendingExecutor)

    with pytest.raises(HostReadinessError, match="migrations"):
        assert_host_ready(marker)


def test_a_v2_marker_with_empty_restore_lists_still_reads(tmp_path):
    from apps.backup.host_marker import parse_marker
    payload = marker_payload(MarkerState.NORMAL, _identity())
    legacy = {**payload, "version": 2, "readiness": {"reservations": [], "fences": [], "not_restored": []}}
    assert parse_marker(legacy) == parse_marker(payload)


@pytest.mark.parametrize("category", ["reservations", "fences", "not_restored"])
def test_a_v2_marker_carrying_retired_restore_facts_is_refused(tmp_path, category):
    from apps.backup.host_marker import MarkerError, parse_marker
    readiness = {"reservations": [], "fences": [], "not_restored": []}
    readiness[category] = [{"schema": "public", "table": "retired"}]
    legacy = {**marker_payload(MarkerState.NORMAL, _identity()), "version": 2, "readiness": readiness}
    with pytest.raises(MarkerError, match="no longer exist"):
        parse_marker(legacy)


def test_readiness_is_reachable_during_quarantine(tmp_path, settings, monkeypatch):
    marker = tmp_path / "marker.json"
    _marker(marker, state=MarkerState.QUARANTINED_AFTER_CUTOVER)
    settings.SPACEWORKS_HOST_MARKER_PATH = marker
    state = DeploymentRecoveryState.load()
    state.mode = DeploymentRecoveryState.Mode.QUARANTINED
    state.save(update_fields=("mode", "updated_at"))
    monkeypatch.setattr("apps.encryption.readiness.assert_ready", lambda: None)

    response = APIClient().get(reverse("readiness"))

    assert response.status_code == 200
    assert response.data["status"] == "ready"

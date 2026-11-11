"""Report GET disclosure audits participate in the tenant migration drain."""

import pytest
from django.db import connections, transaction
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.tenant_migration.gate_locks import SOURCE_GATE_LOCK_NAMESPACE
from tests.events.collab_helpers import client_for
from tests.events.lane_d_helpers import fixture
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db


CASES = [
    ("analytics-generic", "event-registrations", True, "report.previewed"),
    ("report-export", "event-registrations", True, "report.downloaded"),
    ("report-export", "event-attendance", False, "report.downloaded"),
]


def request_report(client, space, event, case):
    route, key, subject, _action = case
    params = {"subject_kind": "event", "subject_id": event.pk} if subject else {}
    return client.get(reverse(route, args=[space.pk, key]), params)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("state", ["draining", "quiesced", "migrated_out"])
def test_frozen_report_get_cannot_append_disclosure_audit(monkeypatch, case, state):
    space, actor, _user, event, _registration = fixture(monkeypatch)
    client = client_for(actor)
    audits = AuditLog.objects.filter(makerspace=space, action=case[3])
    assert request_report(client, space, event, case).status_code == 200
    before = audits.count()
    assert before == 1
    close_gate(space, actor, state=state)

    response = request_report(client, space, event, case)

    assert response.status_code == 423
    assert response.json()["code"] == "tenant_migration_quiesced"
    assert audits.count() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("case", CASES)
def test_report_audit_holds_shared_gate_until_commit(monkeypatch, case):
    space, actor, _user, event, _registration = fixture(monkeypatch)
    secondary = connections["default"].copy()
    observed = []

    def try_exclusive():
        with secondary.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(%s, %s)",
                [SOURCE_GATE_LOCK_NAMESPACE, space.pk],
            )
            return bool(cursor.fetchone()[0])

    def observe_record(*args, **kwargs):
        assert args[1] == case[3]
        assert transaction.get_connection().in_atomic_block
        # Quiescence on another connection cannot pass this in-flight writer.
        assert not try_exclusive()
        result = record(*args, **kwargs)
        assert not try_exclusive()
        transaction.on_commit(lambda: observed.append("committed"))
        observed.append("inserted")
        return result

    monkeypatch.setattr("apps.audit.services.record", observe_record)
    try:
        response = request_report(client_for(actor), space, event, case)
        assert response.status_code == 200
        assert observed == ["inserted", "committed"]
        assert try_exclusive()
        assert AuditLog.objects.filter(makerspace=space, action=case[3]).count() == 1
    finally:
        secondary.close()


def test_direct_subject_preview_cannot_bypass_frozen_gate(monkeypatch):
    from apps.operations.reports import report_data
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed

    space, actor, _user, event, _registration = fixture(monkeypatch)
    close_gate(space, actor)
    with pytest.raises(SourceMigrationGateClosed):
        report_data("event-registrations", space.pk, actor=actor,
                    report_filters={"subject_kind": "event", "subject_id": event.pk})
    assert not AuditLog.objects.filter(makerspace=space, action="report.previewed").exists()


@pytest.mark.parametrize("case", CASES)
def test_unavailable_report_gate_fails_closed_without_audit(monkeypatch, case):
    from apps.tenant_migration.gate_errors import SourceMigrationGateUnavailable

    space, actor, _user, event, _registration = fixture(monkeypatch)

    def unavailable(_makerspace_id):
        raise SourceMigrationGateUnavailable("Lock unavailable")

    monkeypatch.setattr("apps.tenant_migration.gate_runtime.acquire_shared", unavailable)
    response = request_report(client_for(actor), space, event, case)
    assert response.status_code == 503
    assert response.json()["code"] == "tenant_migration_gate_unavailable"
    assert not AuditLog.objects.filter(makerspace=space, action=case[3]).exists()


def test_download_rechecks_gate_after_building_rows(monkeypatch):
    from apps.operations import reports

    space, actor, _user, event, _registration = fixture(monkeypatch)
    original = reports.report_rows

    def freeze_after_build(*args, **kwargs):
        rows = original(*args, **kwargs)
        close_gate(space, actor)
        return rows

    monkeypatch.setattr(reports, "report_rows", freeze_after_build)
    response = request_report(client_for(actor), space, event, CASES[1])
    assert response.status_code == 423
    assert not AuditLog.objects.filter(makerspace=space, action="report.downloaded").exists()


def test_tenant_freeze_does_not_block_deployment_audit(monkeypatch):
    from tests.tenant_migration.source_gate_helpers import make_actor

    space, actor, _user, _event, _registration = fixture(monkeypatch)
    close_gate(space, actor)
    admin = make_actor("aggregate-report")
    response = client_for(admin).get(reverse("report-export-aggregate", args=["event-attendance"]))
    assert response.status_code == 200
    assert AuditLog.objects.filter(makerspace__isnull=True, actor=admin, action="report.downloaded").count() == 1
    assert not AuditLog.objects.filter(makerspace=space, action="report.downloaded").exists()

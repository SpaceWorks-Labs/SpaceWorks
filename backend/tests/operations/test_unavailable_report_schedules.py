"""Retained schedules must fail validation when their runtime report disappears."""

from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.operations.models import ReportSchedule
from apps.operations.report_registry import REPORT_REGISTRY
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("report_key", ["event-attendance", "retired-report"])
@pytest.mark.parametrize("operation", ["patch", "run-now"])
def test_unavailable_schedule_returns_400_without_mutation(monkeypatch, report_key, operation):
    space = make_space("unavailable-schedule")
    manager = make_member("unavailable-manager", space)
    schedule = ReportSchedule.objects.create(
        makerspace=space, created_by=manager, report_key=report_key,
        cadence="daily",
        next_run_at=timezone.now(), recipient_emails=["external@example.test"],
    )
    # Simulate the import-time runtime removal, preserving the persisted row.
    monkeypatch.delitem(REPORT_REGISTRY, report_key, raising=False)
    run = Mock()
    monkeypatch.setattr("apps.operations.views_report_schedules.run_schedule", run)
    client = authenticated_client(manager)
    url = f"/api/v1/admin/report-schedules/{schedule.pk}"
    if operation == "patch":
        response = client.patch(url, {"cadence": "weekly"}, format="json")
    else:
        response = client.post(f"{url}/run-now")

    assert response.status_code == 400, response.data
    assert response.data["report_key"] == ["Report is unavailable on this deployment."]
    run.assert_not_called()
    schedule.refresh_from_db()
    assert schedule.cadence == "daily" and schedule.last_run_at is None
    assert not schedule.deliveries.exists()
    assert not AuditLog.objects.filter(action="report_schedule.updated", target_id=str(schedule.pk)).exists()


def test_unavailable_schedule_can_be_repaired_or_deleted(monkeypatch):
    space = make_space("repair-schedule")
    manager = make_member("repair-manager", space)
    schedule = ReportSchedule.objects.create(
        makerspace=space, created_by=manager, report_key="event-attendance",
        next_run_at=timezone.now(), recipient_emails=["external@example.test"],
    )
    monkeypatch.delitem(REPORT_REGISTRY, "event-attendance")
    client = authenticated_client(manager)
    url = f"/api/v1/admin/report-schedules/{schedule.pk}"
    response = client.patch(url, {"report_key": "most-lent"}, format="json")
    assert response.status_code == 200, response.data
    schedule.refresh_from_db()
    assert schedule.report_key == "most-lent"
    schedule.report_key = "event-attendance"
    schedule.save(update_fields=["report_key"])
    assert client.delete(url).status_code == 204
    assert not ReportSchedule.objects.filter(pk=schedule.pk).exists()

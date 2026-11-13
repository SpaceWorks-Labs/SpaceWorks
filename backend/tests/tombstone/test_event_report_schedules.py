"""Exercise retained schedules with events actually tombstoned at startup."""

import pytest
from django.utils import timezone

from apps.operations.models import ReportSchedule
from apps.operations.report_registry import REPORT_REGISTRY
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("operation", ["patch", "run-now", "delete"])
def test_retained_event_schedule_has_controlled_responses(operation):
    assert "event-attendance" not in REPORT_REGISTRY
    space = make_space("retained-event-schedule")
    manager = make_member("retained-schedule-manager", space)
    schedule = ReportSchedule.objects.create(
        makerspace=space, created_by=manager, report_key="event-attendance",
        cadence=ReportSchedule.Cadence.DAILY,
        next_run_at=timezone.now(), recipient_emails=["external@example.test"],
    )
    client = authenticated_client(manager)
    url = f"/api/v1/admin/report-schedules/{schedule.pk}"
    if operation == "delete":
        assert client.delete(url).status_code == 204
        assert not ReportSchedule.objects.filter(pk=schedule.pk).exists()
        return
    if operation == "patch":
        response = client.patch(url, {"cadence": "weekly"}, format="json")
    else:
        response = client.post(f"{url}/run-now")
    assert response.status_code == 400, response.data
    assert response.data["report_key"] == ["Report is unavailable on this deployment."]
    schedule.refresh_from_db()
    assert schedule.cadence == "daily" and schedule.last_run_at is None
    assert not schedule.deliveries.exists()

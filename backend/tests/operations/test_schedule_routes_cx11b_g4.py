"""Report schedules persist actual settings and generate a real seeded CSV delivery."""
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.operations.models import ReportDelivery, ReportSchedule
from tests.operations.test_inventory_report_routes_cx11b_g4 import seed
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method,key", [(name, method, key) for name, method in [
    ("report-schedules", "GET"), ("report-schedules", "POST"), ("report-schedule-detail", "PATCH"),
    ("report-schedule-detail", "DELETE"), ("report-schedule-run-now", "POST")]
    for key in ("reports", "request_workflow", "loans.enabled") if method != "DELETE" or key == "reports"])
def test_report_schedule_routes_preserve_settings_and_produce_exact_delivery(native, name, method, key, monkeypatch):
    space, client, actor, _product, _issued, _returned = seed(native)
    row = ReportSchedule.objects.create(makerspace=space, report_key="most-lent", format="csv", cadence="weekly",
        next_run_at=timezone.now(), created_by=actor, recipient_emails=["g4-ops@example.test"])
    stored, sent = {}, []
    monkeypatch.setattr("apps.operations.report_schedule_services.store_report_object", lambda key, payload, fmt: stored.__setitem__(key, (payload, fmt)))
    monkeypatch.setattr("apps.operations.report_schedule_services.signed_download_url", lambda key: f"https://storage.example.test/{key}")
    monkeypatch.setattr("apps.operations.serializers_report_schedules.signed_download_url", lambda key: f"https://storage.example.test/{key}")
    monkeypatch.setattr("apps.operations.report_schedule_services.dispatch_email",
        lambda **kwargs: sent.append(kwargs) or SimpleNamespace(status="sent"))
    kwargs = {"makerspace_id": space.pk} if name == "report-schedules" else {"pk": row.pk}
    url = reverse(name, kwargs=kwargs)
    body = {"cadence": "monthly"} if method == "PATCH" else {}
    if name == "report-schedules" and method == "POST":
        body = {"report_key": "most-lent", "format": "csv", "cadence": "daily", "recipient_emails": ["new@example.test"]}
    actions = {("report-schedules", "POST"): ("report_schedule.created",),
        ("report-schedule-detail", "PATCH"): ("report_schedule.updated",),
        ("report-schedule-detail", "DELETE"): ("report_schedule.deleted",),
        ("report-schedule-run-now", "POST"): ("report_schedule.delivered",)}

    def check(response):
        if method == "DELETE":
            assert not ReportSchedule.objects.filter(pk=row.pk).exists()
        elif name == "report-schedule-run-now":
            delivery = ReportDelivery.objects.get(schedule=row)
            assert (delivery.status, delivery.error) == ("sent", "")
            assert stored[delivery.object_key][1] == "csv"
            assert b"Retained drill,1,2" in stored[delivery.object_key][0]
            assert sent[-1]["to_email"] == "g4-ops@example.test"
            assert response.data["status"] == "sent"
            row.refresh_from_db()
            assert row.last_run_at is not None
        elif method == "GET":
            contains(response, row.pk)
            assert response.data["results"][0]["recipient_emails"] == ["g4-ops@example.test"]
        else:
            saved = ReportSchedule.objects.get(pk=response.data["id"])
            assert (saved.report_key, saved.cadence, saved.created_by_id) == ("most-lent", "daily" if method == "POST" else "monthly", actor.pk)
            assert ReportSchedule.objects.filter(makerspace=space).count() == (2 if method == "POST" else 1)
    foreign = outsider(native)
    hidden_list = name == "report-schedules" and method == "GET" and key != "reports"
    def hidden(response):
        assert response.data["results"] == []
    cycle(space, key, lambda: send(client, method, url, body), check,
          off=(200, None) if hidden_list else (404, "module_disabled"), off_check=hidden if hidden_list else None,
          refusal_key="reports" if key == "reports" else "request_workflow",
          on=(201 if name == "report-schedules" and method == "POST" else 204 if method == "DELETE" else 200, None),
          foreign=lambda: send(foreign, method, url, body), foreign_native=native, audit=actions.get((name, method), ()))

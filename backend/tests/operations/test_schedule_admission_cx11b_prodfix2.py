"""537: disabled report sources leave due schedules unclaimed and ready to resume."""
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.operations import report_schedule_services as services
from apps.operations.models import ReportDelivery, ReportSchedule
from tests.modules.test_switch_matrix_objects_rest_support import switch
from tests.payments.switch_helpers_cx11b_p2 import no_policy_writes as no_domain_writes
from tests.operations.route_support_cx11b_g4 import snapshot
from tests.operations.test_inventory_report_routes_cx11b_g4 import seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_reports]


@pytest.mark.parametrize("key", ["reports", "request_workflow", "loans.enabled"])
def test_direct_and_scheduled_execution_preserve_disabled_source_before_claim(key, monkeypatch):
    space, _client, actor, _product, _issued, _returned = seed(False)
    now = timezone.now()
    schedule = ReportSchedule.objects.create(makerspace=space, report_key="most-lent", format="csv",
        cadence="weekly", next_run_at=now, created_by=actor, recipient_emails=["resume@example.test"])
    stored, sent = [], []
    monkeypatch.setattr(services, "store_report_object", lambda *args: stored.append(args))
    monkeypatch.setattr(services, "signed_download_url", lambda key: f"https://storage.example.test/{key}")
    monkeypatch.setattr(services, "dispatch_email",
        lambda **kwargs: sent.append(kwargs) or SimpleNamespace(status="sent"))
    original = switch(space, key)
    before = snapshot()
    counts = {"delivered": 0, "failed": 0, "skipped": 0}
    with no_domain_writes():
        assert services.run_schedule(schedule.pk, now=now, force=True, counts=counts) is None
        swept = services.run_report_schedules(now=now)
    assert counts == {"delivered": 0, "failed": 0, "skipped": 1}
    assert swept == {"delivered": 0, "failed": 0, "skipped": 0 if key == "reports" else 1}
    assert snapshot() == before
    schedule.refresh_from_db()
    assert (schedule.next_run_at, schedule.last_run_at) == (now, None)
    assert not ReportDelivery.objects.filter(schedule=schedule).exists()
    assert not AuditLog.objects.filter(action="report_schedule.skipped", meta__schedule_id=schedule.pk).exists()
    assert (stored, sent) == ([], [])

    switch(space, key, original=original)
    assert services.run_report_schedules(now=now) == {"delivered": 1, "failed": 0, "skipped": 0}
    schedule.refresh_from_db()
    assert schedule.last_run_at == now
    assert schedule.next_run_at > now
    delivery = ReportDelivery.objects.get(schedule=schedule)
    assert (delivery.status, delivery.error) == ("sent", "")
    assert len(stored) == len(sent) == 1
    assert stored[0][0] == delivery.object_key
    assert stored[0][2] == "csv"
    assert b"Retained drill,1,2" in stored[0][1]
    assert sent[0]["to_email"] == "resume@example.test"
    assert list(AuditLog.objects.filter(meta__schedule_id=schedule.pk).values_list("action", flat=True)) == [
        "report_schedule.delivered"]
    written = snapshot()
    with no_domain_writes():
        assert services.run_report_schedules(now=now) == {"delivered": 0, "failed": 0, "skipped": 0}
    assert snapshot() == written
    assert len(stored) == len(sent) == 1


def test_direct_fence_records_and_blocks_even_a_swallowed_write():
    from django.db import connection
    with pytest.raises(AssertionError, match="UPDATE cx11b_forbidden"):
        with no_domain_writes():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE cx11b_forbidden SET value = 1")
            except AssertionError:
                pass  # A fail-safe adapter must not hide the recorded attempt.

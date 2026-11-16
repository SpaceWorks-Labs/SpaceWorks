from datetime import timedelta

import pytest
from apps.makerspaces.models import MakerspaceMembership
from django.utils import timezone

from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.operations.models import StocktakeSession
from apps.operations.models_report_schedules import ReportDelivery, ReportSchedule
from apps.operations.notifications_p2_alerts import notify_email_failure, notify_stocktake
from apps.operations.notifications_p2_reports import notify_report

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("event", ["scheduled", "completed"])
def test_stocktake_rows_only_reach_inventory_authority(lane, event):
    row = StocktakeSession.objects.create(makerspace=lane.space, started_by=lane.manager,
        status="completed" if event == "completed" else "counting",
        completed_at=timezone.now() if event == "completed" else None)
    notify_stocktake(row, event)
    envelope = lane.deliver(event, lane.manager)
    assert source_eligible(envelope)
    assert not NotificationEnvelope.objects.filter(recipient=lane.owner).exists()
    row.status = "cancelled"
    row.save(update_fields=["status"])
    assert resolve(envelope) == []


def test_first_email_failure_is_deduplicated_and_does_not_recurse(lane):
    # The real save signal owns the adapter call, including a second save.
    log = EmailLog.objects.create(makerspace=lane.space, to_email="private@example.test",
        subject="Private subject", text_body="Private body", stream="membership", event="approved",
        status="failed", attempts=1)
    log.save(update_fields=["status"])
    envelope = lane.deliver("email.failed", lane.manager)
    assert source_eligible(envelope)
    assert NotificationEnvelope.objects.filter(event="email.failed").count() == 1
    assert "Private" not in lane.fake.calls[-1][1]["text"]
    assert "private@example.test" not in envelope.message_body
    alert_transport = EmailLog.objects.create(makerspace=lane.space, to_email=lane.manager.email,
        subject="Email delivery failed", stream="integrations", event="email.failed", status="failed", attempts=1)
    notify_email_failure(alert_transport)
    assert NotificationEnvelope.objects.filter(event="email.failed").count() == 1
    log.status = "sent"
    log.save(update_fields=["status"])
    assert not source_eligible(envelope)


def test_report_role_selection_rechecks_creator_and_never_sends_download_bearer(lane):
    schedule = ReportSchedule.objects.create(makerspace=lane.space, report_key="most-lent", created_by=lane.manager,
        next_run_at=timezone.now(), recipient_roles=["space_manager"])
    delivery = ReportDelivery.objects.create(schedule=schedule, status="sent", object_key="reports/private.csv",
        expires_at=timezone.now()+timedelta(hours=1))
    notify_report(delivery)
    envelope = lane.deliver("scheduled_report", lane.manager)
    assert source_eligible(envelope)
    assert "reports/private.csv" not in envelope.message_body
    assert "token=" not in envelope.message_body
    assert lane.fake.calls[-1][1]["link"] == f"/m/{lane.space.slug}/admin/reports"
    assert not NotificationEnvelope.objects.filter(recipient=lane.owner).exists()
    MakerspaceMembership.all_tracks.filter(user=lane.manager).update(status="revoked")
    assert resolve(envelope) == []


def test_explicit_report_address_does_not_establish_a_personal_endpoint_recipient(lane):
    schedule = ReportSchedule.objects.create(makerspace=lane.space, report_key="most-lent", created_by=lane.manager,
        next_run_at=timezone.now(), recipient_emails=[lane.owner.email])
    delivery = ReportDelivery.objects.create(schedule=schedule, status="sent", object_key="reports/private.csv",
        expires_at=timezone.now()+timedelta(hours=1))
    notify_report(delivery)
    assert not NotificationEnvelope.objects.exists()

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from django.utils import timezone

from apps.events.services_broadcasts import change
from apps.integrations.delivery_sources import DeliverySource, SOURCES, register
from apps.integrations.delivery_content import content, render
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.models import EmailLog
from apps.integrations.reminders_deferred import _digest, dispatch
from apps.operations.models_reminders import ReminderSchedule
from tests.events.lane_d_helpers import fixture, queued, smtp

pytestmark = pytest.mark.django_db


def test_campaign_excluded_from_assignment_and_legacy_digest(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    now = timezone.now()
    due = now + timedelta(hours=1)
    monkeypatch.setattr("apps.integrations.digests.digest_due", lambda *args: due)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    assert not log.error.startswith("deferred:digest:")
    log.error = f"deferred:digest:{due.isoformat()}"; log.save(update_fields=["error"])
    change(campaign, actor, "cancel")
    send = smtp(monkeypatch)
    _digest(space, SimpleNamespace(subject=f"digest:{user.pk}:{due.isoformat()}"), due)
    assert not send.called
    assert not EmailLog.objects.filter(event="daily_digest").exists()


def test_quiet_release_rechecks_cancelled_campaign(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    now = timezone.now(); due = now + timedelta(hours=1)
    monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", lambda *args: due)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    assert log.error.startswith("deferred:email:")
    row = ReminderSchedule.objects.get(source="notifications.deferred", subject__startswith=f"email:{log.pk}:")
    change(campaign, actor, "cancel")
    monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", lambda *args: None)
    send = smtp(monkeypatch)
    dispatch(space, row, None, due, None)
    log.refresh_from_db()
    assert not send.called and log.status == "skipped"


def test_digest_retains_source_references_and_rebuilds_on_retry(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    now = timezone.now(); due = now + timedelta(hours=1)
    live = {1, 2}
    def prepare(log):
        if log.source_id not in live:
            return False
        render(log, subject=log.subject, text_body=f"current occurrence {log.source_id}")
        return True
    monkeypatch.setitem(SOURCES, "test_occurrence", DeliverySource(prepare))
    monkeypatch.setattr("apps.integrations.digests.digest_due", lambda *args: due)
    mails = [dispatch_email(makerspace=space, recipient_id=user.pk, to_email=user.email, feature="events",
                            stream="events", event="reminder", audience="requester", subject=f"Occurrence {pk}",
                            text_body="original", source_kind="test_occurrence", source_id=pk,
                            source_metadata={"revision": 1}) for pk in (1, 2)]
    monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", lambda *args: None)
    _digest(space, SimpleNamespace(subject=f"digest:{user.pk}:{due.isoformat()}"), due)
    summary = EmailLog.objects.get(source_kind="notification_digest")
    assert summary.source_metadata == {"entries": [m.pk for m in mails]}
    # Invalidate after summary assembly; retry must not send its frozen body.
    live.remove(1)
    send = smtp(monkeypatch); send.side_effect = OSError("offline")
    _deliver(summary)
    assert summary.status == "failed"
    assert "current occurrence 1" not in content(summary).text_body and "current occurrence 2" in content(summary).text_body
    live.clear(); send.reset_mock(); send.side_effect = None
    _deliver(summary)
    assert summary.status == "skipped" and not send.called


def test_unknown_source_fails_closed(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    log = dispatch_email(makerspace=space, to_email=user.email, subject="stale", text_body="private",
                         source_kind="removed_domain", source_id=1)
    send = smtp(monkeypatch)
    _deliver(log)
    assert log.status == "skipped" and not send.called


def test_timing_failure_never_sends_source_backed_content(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    def broken(*args):
        raise OSError("timing unavailable")
    monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", broken)
    send = smtp(monkeypatch)
    _deliver(log)
    assert log.status == "failed" and log.error == "delivery_timing_unavailable" and not send.called

"""Real source rendering must send without mutating encrypted outbox attributes."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from apps.events.services_bulk_invites import bulk_invites
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.models import EmailLog
from apps.integrations.reminders_deferred import _digest
from tests.encryption.conftest import enabled_encryption
from tests.events.lane_d_helpers import fixture, queued, smtp

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("kind", ["event_broadcast", "event_invitation", "notification_digest"])
def test_source_mail_sends_and_rebuilds_with_strict_encrypted_reads(monkeypatch, kind):
    with enabled_encryption(dual_read=False):
        space, actor, user, event, registration = fixture(monkeypatch)
        if kind == "event_broadcast":
            campaign, delivery, log = queued(event, actor, statuses=["registered"])
            expected = event.title
        elif kind == "event_invitation":
            bulk_invites(event, actor, [user.email])
            log = EmailLog.objects.get(source_kind=kind)
            expected = f"You're invited to {event.title}"
        else:
            due = timezone.now() + timedelta(hours=1)
            monkeypatch.setattr("apps.integrations.digests.digest_due", lambda *args: due)
            dispatch_email(makerspace=space, to_email=user.email, recipient_id=user.pk, feature="events",
                           stream="events", event="reminder", audience="requester",
                           subject="Reminder", text_body="Strict encrypted digest entry")
            _digest(space, SimpleNamespace(subject=f"digest:{user.pk}:{due.isoformat()}"), due)
            log = EmailLog.objects.get(source_kind=kind)
            expected = "Reminder\nStrict encrypted digest entry"
        # Exercise fresh DB reads, rather than the save-boundary's plaintext cache.
        log = EmailLog.objects.get(pk=log.pk)
        mapped = ("to_email", "subject", "text_body", "html_body")
        raw = {name: log.__dict__[name] for name in mapped}
        assert raw["subject"].startswith("pii:gcm:v1:")
        send = smtp(monkeypatch)
        send.side_effect = OSError("SMTP temporarily offline")
        message = Mock(wraps=EmailMultiAlternatives)
        monkeypatch.setattr("apps.integrations.dispatch_delivery.EmailMultiAlternatives", message)
        _deliver(log)
        assert log.status == "failed"
        send.side_effect = None
        _deliver(log)
        assert log.status == "sent" and send.call_count == 2
        assert expected in message.call_args.kwargs["body"]
        assert message.call_args.kwargs["to"] == [user.email]
        assert str(registration.checkin_token) not in message.call_args.kwargs["body"]
        assert {name: log.__dict__[name] for name in mapped} == raw
        persisted = EmailLog.objects.get(pk=log.pk)
        assert {name: persisted.__dict__[name] for name in mapped} == raw
        # All mapped reads still pass the strict contract after rendering/saves.
        assert persisted.to_email == user.email
        assert persisted.subject

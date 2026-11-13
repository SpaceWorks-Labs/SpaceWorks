"""Explicit invitation policy is identical before and after quiet hours."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.services_bulk_invites import bulk_invites
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.email_preferences import address_hash
from apps.integrations.models import EmailLog, NotificationPreference
from apps.integrations.models_suppression import EmailSuppression
from apps.integrations.reminders_deferred import dispatch
from apps.notifications.models_inbox import MemberNotificationPreference
from apps.operations.models_reminders import ReminderSchedule
from tests.events.lane_d_helpers import fixture, smtp

pytestmark = pytest.mark.django_db


def configure_timing(monkeypatch, deferred):
    due = timezone.now() + timedelta(hours=1)
    monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until",
                        lambda *args: due if deferred else None)
    return due


def deliver(monkeypatch, space, log, due, deferred):
    if deferred:
        assert log.status == "pending" and log.error.startswith("deferred:email:")
        row = ReminderSchedule.objects.get(
            source="notifications.deferred", subject__startswith=f"email:{log.pk}:",
        )
        monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", lambda *args: None)
        dispatch(space, row, None, due, None)
    else:
        _deliver(log)
    log.refresh_from_db()


@pytest.mark.parametrize("matrix", [None, False, True])
@pytest.mark.parametrize("deferred", [False, True])
@pytest.mark.parametrize("known_account", [False, True])
def test_explicit_invitation_delivery_does_not_depend_on_matrix_or_timing(
    monkeypatch, matrix, deferred, known_account,
):
    space, actor, user, event, _registration = fixture(monkeypatch, email_enabled=False)
    if matrix is not None:
        NotificationPreference.objects.create(
            makerspace=space, feature="events", channel="email", enabled=matrix,
        )
    due = configure_timing(monkeypatch, deferred)
    address = user.email if known_account else "new-invitee@example.test"
    bulk_invites(event, actor, [address])
    log = EmailLog.objects.get(source_kind="event_invitation")
    assert log.recipient_id == (user.pk if known_account else None)
    send = smtp(monkeypatch)

    deliver(monkeypatch, space, log, due, deferred)

    assert log.status == "sent" and send.call_count == 1
    assert not log.text_body and not log.html_body
    # Releasing an already delivered claim must not send the invitation again.
    _deliver(log)
    assert send.call_count == 1


@pytest.mark.parametrize("deferred", [False, True])
@pytest.mark.parametrize("block", ["email_module", "opt_out", "suppressed", "revoked", "expired", "sender", "invites_feature"])
def test_invitation_policy_rechecks_blocks_at_actual_delivery(monkeypatch, deferred, block):
    space, actor, user, event, _registration = fixture(monkeypatch)
    due = configure_timing(monkeypatch, deferred)
    bulk_invites(event, actor, [user.email])
    log = EmailLog.objects.get(source_kind="event_invitation")
    if block == "email_module":
        space.enabled_modules.remove("email")
        space.save(update_fields=["enabled_modules"])
    elif block == "opt_out":
        MemberNotificationPreference.objects.create(
            makerspace=space, user=user, feature="events", channel="email", enabled=False,
        )
    elif block == "suppressed":
        EmailSuppression.objects.create(makerspace=space,
            address_hash=address_hash(space.pk, user.email), reason="complaint")
    elif block in {"revoked", "expired"}:
        invite = event.invites.get()
        field = "revoked_at" if block == "revoked" else "expires_at"
        setattr(invite, field, timezone.now() - timedelta(seconds=1))
        invite.save(update_fields=[field])
    elif block == "sender":
        actor.is_active = False
        actor.save(update_fields=["is_active"])
    else:
        space.enabled_features.remove("events.invites")
        space.save(update_fields=["enabled_features"])
    send = smtp(monkeypatch)

    deliver(monkeypatch, space, log, due, deferred)

    assert log.status == "skipped" and not send.called


def test_deferred_automatic_event_mail_still_honours_disabled_matrix(monkeypatch):
    space, _actor, user, _event, _registration = fixture(monkeypatch, email_enabled=False)
    due = configure_timing(monkeypatch, True)
    log = dispatch_email(makerspace=space, to_email=user.email, recipient_id=user.pk,
                         subject="Automatic reminder", text_body="Reminder", feature="events",
                         stream="events", event="reminder", audience="requester")
    send = smtp(monkeypatch)

    deliver(monkeypatch, space, log, due, True)

    assert log.status == "skipped" and not send.called
    assert log.error == "notification_disabled_before_release"

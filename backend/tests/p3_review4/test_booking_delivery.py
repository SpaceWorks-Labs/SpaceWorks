from types import SimpleNamespace

import pytest

from apps.bookings.notifications import notify_booking_status
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope

pytestmark = pytest.mark.django_db


def capture_payload(monkeypatch):
    calls = []
    def capture(*args, **kwargs):
        calls.append(kwargs["build"]())
    monkeypatch.setattr("apps.bookings.notifications.notify_lifecycle", capture)
    return calls


def test_staff_matrix_owns_inbox_push_but_owner_envelope_keeps_its_legs(world, monkeypatch):
    capture_payload(monkeypatch)
    notify_booking_status(world.booking, "confirmed")
    staff = NotificationEnvelope.objects.get(source_kind="bookings.lifecycle", audience="staff", recipient=world.staff)
    assert set(staff.deliveries.values_list("channel", "state", "last_error")) == {
        ("in_app", "skipped", "legacy_matrix_channel"), ("native_push", "skipped", "legacy_matrix_channel")}
    owner = NotificationEnvelope.objects.get(source_kind="bookings.lifecycle", audience="requester", recipient=world.owner)
    assert not owner.deliveries.filter(channel__in=["in_app", "native_push"], state="skipped").exists()
    notify_booking_status(world.booking, "confirmed")
    assert NotificationDelivery.objects.filter(envelope=staff).count() == 2


@pytest.mark.parametrize("event", ["rejected", "cancelled"])
def test_guest_reasons_are_visible_and_retry_content_is_source_bound(world, monkeypatch, event):
    calls = capture_payload(monkeypatch)
    row = world.booking
    row.member = None
    row.status, row.decision_reason = event, '<b>Closed & unavailable</b>'
    row.save()
    monkeypatch.setattr("apps.bookings.notifications.render", lambda *_args, **_kwargs: {
        "subject": "Booking update", "text_body": "Decision", "html_body": "<p>Decision</p>"})
    notify_booking_status(row, event)
    message = calls[0].emails[0]
    assert row.decision_reason in message.text_body
    assert not message.html_body  # Mail clients must render the reason-bearing text.
    assert message.source_kind == "bookings.guest_mailbox"
    from apps.bookings.notification_guest_mail import prepare
    from apps.integrations.delivery_content import content
    log = SimpleNamespace(makerspace_id=world.space.pk, source_id=row.pk, event=event, audience="requester",
        source_metadata=message.source_metadata, to_email=row.email)
    assert prepare(log)
    assert row.decision_reason in content(log).text_body and not content(log).html_body
    # A terminal booking cannot be reopened; a newer revision alone must invalidate queued guest mail.
    type(row).objects.filter(pk=row.pk).update(calendar_sequence=row.calendar_sequence + 1)
    assert not prepare(log)


def test_guest_mail_refuses_new_account_owner_and_contact_changes(world, monkeypatch):
    calls = capture_payload(monkeypatch)
    row = world.booking
    row.member = None
    row.save()
    notify_booking_status(row, "confirmed")
    message = calls[0].emails[0]
    from apps.bookings.notification_guest_mail import prepare
    log = SimpleNamespace(makerspace_id=world.space.pk, source_id=row.pk, event="confirmed", audience="requester",
        source_metadata=message.source_metadata, to_email=row.email)
    row.email = "changed@example.test"
    row.save()
    assert not prepare(log)
    row.email, row.member = log.to_email, world.owner
    row.save()
    assert not prepare(log)

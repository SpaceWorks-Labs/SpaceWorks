"""Owner-only ticket renders and the post-commit restored lifecycle contract."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone
from icalendar import Calendar
from PIL import Image

from apps.audit.models import AuditLog
from apps.events import notifications, services
from apps.events.models import EventRegistration
from apps.events.services_calendar import render_member_calendar
from apps.events.services_registration_tools import restore_registration
from apps.events.views_ticket import TicketRenderThrottle
from apps.integrations import notify
from apps.integrations.email_templates_registry import get_entry
from apps.integrations.models import NotificationPreference
from apps.integrations.notification_catalog import FEATURE_EVENTS
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


def fixture():
    space = event_space("lane-b-ticket")
    staff, owner = make_staff(space), account("ticket-owner")
    event = open_event(space)
    row = services.register(event, member=owner, actor=staff, staff_registration=True)
    return space, staff, owner, event, row


def ticket_url(space, row, extension="ticket.png"):
    return f"/api/v1/member/makerspaces/{space.pk}/event-registrations/{row.pk}/{extension}"


@pytest.mark.parametrize("state", ["registered", "attended"])
def test_owner_downloads_valid_no_store_png_with_an_audit(state):
    space, _, owner, _, row = fixture()
    row.status = state; row.save(update_fields=["status"])
    response = client_for(owner).get(ticket_url(space, row))
    assert response.status_code == 200 and response["Content-Type"] == "image/png"
    assert "no-store" in response["Cache-Control"]
    with Image.open(BytesIO(response.content)) as image:
        assert image.format == "PNG" and image.width >= 640
        image.verify()
    audit = AuditLog.objects.get(action="event.ticket_downloaded")
    assert audit.actor == owner and audit.target_id == str(row.pk)
    assert str(row.checkin_token) not in str(audit.meta)


@pytest.mark.parametrize("state", ["pending_approval", "waitlisted", "cancelled", "rejected"])
def test_unconfirmed_or_terminal_registration_has_no_ticket_png(state):
    space, _, owner, _, row = fixture()
    row.status = state; row.save(update_fields=["status"])
    response = client_for(owner).get(ticket_url(space, row))
    assert response.status_code == 404 and not AuditLog.objects.filter(action="event.ticket_downloaded").exists()


def test_foreign_account_or_tenant_cannot_download_ticket_or_read_its_details():
    space, staff, owner, _, row = fixture()
    stranger = account("ticket-stranger")
    foreign = event_space("ticket-foreign")
    for extension in ("ticket.png", "ticket/"):
        assert client_for(stranger).get(ticket_url(space, row, extension)).status_code == 404
        # Staff authority is a staff-track row, not community membership (U-A1): to the ticket routes a
        # staffer who is not the holder is simply a non-owner, so the answer is the same 404 (no enumeration).
        assert client_for(staff).get(ticket_url(space, row, extension)).status_code == 404
        assert client_for(owner).get(ticket_url(foreign, row, extension)).status_code == 404
    assert not AuditLog.objects.filter(action="event.ticket_downloaded").exists()


def test_cancelled_event_cannot_render_a_still_registered_ticket():
    space, staff, owner, event, row = fixture()
    services.cancel(event, actor=staff)
    assert client_for(owner).get(ticket_url(space, row)).status_code == 404
    details = client_for(owner).get(ticket_url(space, row, "ticket/"))
    assert details.status_code == 200 and details.data["ticket_png_available"] is False
    assert details.data["status"] == "registered"
    assert details.data["event"]["status"] == "cancelled"


def test_owned_ticket_details_have_only_authorized_event_fields_and_no_credential():
    space, _, owner, event, row = fixture()
    response = client_for(owner).get(ticket_url(space, row, "ticket/"))
    assert response.status_code == 200 and "no-store" in response["Cache-Control"]
    # The live-ticket serializer adds the owner's own attendance stamp and credential
    # mode (legacy/v2/inert, never the credential itself) and the event id.
    assert set(response.data) == {"registration_id", "status", "event", "ticket_png_available",
                                  "attended_at", "credential_mode", "delivery_mode", "map_url", "join_url",
                                  "pay_by"}  # Parity E-B5: the end of an open pay window
    assert set(response.data["event"]) == {"id", "status", "title", "description", "starts_at", "ends_at", "location", "public_token", "timezone_name"}
    assert response.data["event"]["status"] == "published"
    assert response.data["registration_id"] == row.pk and response.data["event"]["title"] == event.title
    assert owner.email not in str(response.data) and str(row.checkin_token) not in str(response.data)


def test_png_render_throttle_has_a_bounded_shared_budget_and_does_not_audit_refusals(monkeypatch):
    space, _, owner, _, row = fixture()
    monkeypatch.setattr(TicketRenderThrottle, "rate", "2/hour")
    monkeypatch.setattr("apps.events.views_ticket.render_confirmation_png", lambda **kwargs: b"bounded png")
    client = client_for(owner)
    assert client.get(ticket_url(space, row)).status_code == 200
    assert client.get(ticket_url(space, row)).status_code == 200
    assert client.get(ticket_url(space, row)).status_code == 429
    assert AuditLog.objects.filter(action="event.ticket_downloaded").count() == 2


def test_restored_notification_is_registered_for_both_audiences_with_nonsecret_context():
    assert "registration_restored" in FEATURE_EVENTS["events"]
    assert "registration_restored" in notifications.EVENT_NOTIFICATION_EVENTS
    for audience in ("staff", "requester"):
        entry = get_entry("events", audience, "registration_restored")
        assert entry is not None and entry.default_subject
        assert "checkin_token" not in str(entry.fields) and "custom_answers" not in str(entry.fields)


def test_verified_owner_is_notified_only_after_restore_commits(django_capture_on_commit_callbacks, monkeypatch):
    # Phase 2: the owner notice is a source-backed envelope written in the restore
    # transaction and handed to the outbox only once that transaction commits.
    from apps.integrations.models_contract import NotificationEnvelope
    space, staff, owner, event, row = fixture()
    queued = []
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", queued.append)
    cancelled = services.cancel_registration(row, actor=staff)
    queued.clear()
    with django_capture_on_commit_callbacks(execute=True):
        restored = restore_registration(cancelled, actor=staff)
        owner_env = NotificationEnvelope.objects.get(event="registration_restored", audience="requester")
        assert queued == []
    assert owner_env.pk in queued and owner_env.recipient_id == owner.pk
    assert owner_env.context["registration_id"] == restored.pk
    assert str(row.checkin_token) not in owner_env.message_body


def test_rolled_back_restore_never_dispatches_or_leaves_a_restored_audit(django_capture_on_commit_callbacks, monkeypatch):
    space, staff, owner, _, row = fixture()
    owner.email_verified_at = timezone.now(); owner.save(update_fields=["email_verified_at"])
    NotificationPreference.objects.create(makerspace=space, feature="events", channel="email", enabled=True)
    cancelled = services.cancel_registration(row, actor=staff)
    deliveries = []
    monkeypatch.setattr(notify, "dispatch_email", lambda **kwargs: deliveries.append(kwargs))
    # Commands refuse a caller's transaction, so the failure is raised inside the
    # command's own atomic block, after the restore, audit and notification writes.
    def fail_after_writes(row):
        raise RuntimeError("rollback")

    monkeypatch.setattr(services, "_refresh", fail_after_writes)
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError, match="rollback"):
            restore_registration(cancelled, actor=staff)
    row.refresh_from_db()
    assert row.status == "cancelled" and deliveries == []
    assert not AuditLog.objects.filter(action="event.registration_restored").exists()


def test_member_calendar_sequence_and_status_reflect_cancel_then_restore():
    space, staff, _, _, row = fixture()
    cancelled = services.cancel_registration(row, actor=staff)
    registrations = EventRegistration.objects.filter(pk=row.pk)
    before = Calendar.from_ical(render_member_calendar(space, registrations)).walk("VEVENT")[0]
    restore_registration(cancelled, actor=staff)
    after = Calendar.from_ical(render_member_calendar(space, registrations)).walk("VEVENT")[0]
    assert str(before["status"]) == "CANCELLED" and str(after["status"]) == "CONFIRMED"
    assert after["sequence"] > before["sequence"] and after["uid"] == before["uid"]


@pytest.mark.django_db(transaction=True)
def test_real_committed_restoration_reaches_staff_and_owner_through_outbox_delivery(settings, monkeypatch, mailoutbox):
    from apps.integrations.models import EmailLog
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_tasks import deliver_envelope

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    space, staff, owner, _, row = fixture()
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "email"})
    space.save(update_fields=["enabled_modules"])
    for person in (staff, owner):
        person.email_verified_at = timezone.now(); person.save(update_fields=["email_verified_at"])
    NotificationPreference.objects.create(makerspace=space, feature="events", channel="email", enabled=True)
    queued = []
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", queued.append)
    cancelled = services.cancel_registration(row, actor=staff)
    queued.clear()
    restored = restore_registration(cancelled, actor=staff)  # the command commits its own transaction
    rows = NotificationEnvelope.objects.filter(event="registration_restored").exclude(source_kind="legacy.lifecycle")
    assert {(env.audience, env.recipient_id) for env in rows} == {("staff", staff.pk), ("requester", owner.pk)}
    for envelope in rows:
        assert envelope.pk in queued
        deliver_envelope(envelope.pk)
    logs = EmailLog.objects.filter(makerspace=space, event="registration_restored")
    assert {log.to_email for log in logs} == {staff.email, owner.email}
    assert all(str(row.checkin_token) not in log.text_body for log in logs)
    assert {tuple(message.to) for message in mailoutbox} == {(staff.email,), (owner.email,)}
    assert all(restored.status in message.body for message in mailoutbox)

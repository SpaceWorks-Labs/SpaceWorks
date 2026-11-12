from types import SimpleNamespace as Bag
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from tests.p3_review3.test_notification_routes import assert_links, routes  # noqa: F401

pytestmark = pytest.mark.django_db


def test_event_booking_and_certificate_emitters_use_route_mode(routes, monkeypatch):
    from apps.events import broadcast_channels, notification_envelopes as events, reminders as event_reminders

    calls = []
    message = {"subject": "Update", "text_body": "Body", "html_body": ""}
    monkeypatch.setattr("apps.integrations.notification_outbox.emit", lambda **kwargs: calls.append(kwargs) or Bag())
    monkeypatch.setattr("apps.integrations.models_contract.NotificationDelivery.objects.get_or_create", lambda **_: None)
    monkeypatch.setattr("apps.events.broadcasts.render_recipient", lambda *_: message)
    monkeypatch.setattr(events, "emit", lambda **kwargs: calls.append(kwargs) or Bag())
    home = routes.home
    row = Bag(pk=4, status="registered", member=routes.owner, member_id=routes.owner.pk,
              registered_via_makerspace=home, event_id=1)
    event = Bag(pk=1, title="Workshop", makerspace=home, starts_at=timezone.now())
    row.event = event
    monkeypatch.setattr(event_reminders, "_eligible", lambda *_: row)
    monkeypatch.setattr(event_reminders, "_recipient", lambda *_: routes.owner)
    monkeypatch.setattr(event_reminders, "events_context", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(event_reminders, "render", lambda *_: message)
    monkeypatch.setattr(event_reminders, "emit", lambda **kwargs: calls.append(kwargs))
    event_reminders.dispatch_event_reminder(home, Bag(pk=2, subject="4:starts", offset_seconds=-3600), None, timezone.now(), ZoneInfo("UTC"))
    assert len(calls) == 1
    events.certificate_envelope(Bag(pk=3, revision=1, registration=row), "certificate_ready")
    # A legacy (schema 1) campaign: delivery_revision reads render_schema_version (the model default).
    broadcast_channels.emit_channels(Bag(pk=4, makerspace=home, event_id=1, render_schema_version=1), routes.owner)
    assert len(calls) == 3
    assert_links(routes, [("event reminder", calls[0]["rendered"], "member/events/4/ticket"),
                          ("certificate", calls[1]["rendered"], "member"),
                          ("event campaign", calls[2]["rendered"], "member")])


def test_booking_reminder_and_campaign_routes(routes, monkeypatch):
    from apps.bookings import broadcasts_personal as campaigns, reminder_envelopes as reminders

    calls = []
    message = {"subject": "Update", "text_body": "Body", "html_body": ""}
    monkeypatch.setattr("apps.integrations.notification_outbox.emit", lambda **kwargs: calls.append(kwargs) or Bag())
    monkeypatch.setattr("apps.bookings.notification_owner_mailbox.notify_owner", lambda _: None)
    monkeypatch.setattr(reminders, "context_for", lambda _: {})
    row = Bag(pk=4, calendar_sequence=1, space=Bag(makerspace=routes.home),
              starts_at=timezone.now(), ends_at=timezone.now())
    assert reminders.emit_reminder(row, Bag(pk=5, offset_seconds=-3600), routes.owner)
    selection = Mock()
    selection.filter.return_value.order_by.return_value.first.return_value = row
    monkeypatch.setattr("apps.bookings.broadcasts.bookings", lambda _: selection)
    monkeypatch.setattr(campaigns, "render", lambda *_: message)
    campaign = Bag(pk=3, makerspace=routes.home, space=Bag(name="Workshop"), subject="News", body="Body")
    body = campaigns.personal_content(campaign, routes.owner)
    assert len(calls) == 1
    assert_links(routes, [("booking reminder", calls[0]["rendered"], "member/bookings"),
                          ("booking campaign", body, "member/bookings")])


def test_equipment_owner_emitters_use_local_routes(routes, lane, monkeypatch):
    from apps.hardware_requests import notifications_p2_reminders as loans, notifications_p2_requests as hardware
    from apps.machines import notifications_p2_certifications as certifications, notifications_p2_service as service
    from apps.hardware_requests.models import HardwareRequest

    calls = []
    message = {"subject": "Update", "text_body": "Body", "html_body": ""}
    for module in (hardware, loans, certifications, service):
        monkeypatch.setattr(module, "fanout", lambda **kwargs: calls.append(kwargs) or Bag(scheduled=True))
        monkeypatch.setattr(module, "render", lambda *_args, **_kwargs: dict(message))
    monkeypatch.setattr(hardware, "hardware_context", lambda *_args, **_kwargs: {})
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_contact.notify", lambda *_: None)
    loan = HardwareRequest.objects.create(makerspace=routes.home, requester=routes.owner, status="issued",
                                           return_due_at=timezone.now())
    hardware.notify_request(loan, "return_reminder")
    monkeypatch.setattr(loans, "hardware_context", lambda *_args, **_kwargs: {"request": Bag()})
    loans.deliver(routes.home, loan, Bag(kind="overdue", offset_seconds=0), Bag(body="Return it"), ZoneInfo("UTC"))
    machine_type = Bag(pk=2)
    job = Bag(pk=6, makerspace=routes.home, status="accepted", updated_at=timezone.now(),
        member=routes.owner, requester=routes.owner, member_id=routes.owner.pk, requester_id=routes.owner.pk,
        queue_id=2, queue=Bag(machine_type=machine_type), bucket_id=None, assigned_machine_id=None)
    monkeypatch.setattr("apps.machines.service_printing_emails._is_printer_request", lambda _: False)
    monkeypatch.setattr(service, "scope_for", lambda _: None)
    # The stub job lacks the real request fields the printing projection reads.
    monkeypatch.setattr("apps.machines.service_printing_emails._projection", lambda _row: None)
    monkeypatch.setattr(service, "printing_context", lambda *_args, **_kwargs: {})
    service.notify_service(job, "accepted")  # started/completed/cancelled owner legs are durable service_queue_notices now
    grant = Bag(pk=7, certification_type=Bag(makerspace=routes.home, name="Safety", machine_type_id=2),
        expires_at=None, granted_at=timezone.now(), revoked_at=None, membership_id=8,
        membership=Bag(user=routes.owner))
    certifications.notify(grant, "granted")
    assert len(calls) == 4  # Fail-safe decorators must not hide a broken test setup.
    assert_links(routes, [(name, call["own"], "member") for name, call in zip(
        ("hardware", "loan reminder", "machine service", "certification"), calls, strict=True)])

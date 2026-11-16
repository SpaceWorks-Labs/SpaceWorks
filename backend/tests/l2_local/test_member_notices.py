"""G7 member notices: removal after the undo window, ticket re-send, 12 h skip; L1 join link."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.audit.services import record
from apps.events.models import EventRegistration
from apps.events.notices_r2_l2 import removal_eligible, resend_tickets, with_join_url
from apps.events.reminders import fresh_signup
from apps.events.services_registration import register
from apps.events.services_registration_state import cancel_registration
from apps.integrations.models_contract import NotificationEnvelope
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


def registered(slug="notices"):
    space = event_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "email"})
    space.save(update_fields=["enabled_modules"])
    staff = make_staff(space)
    member = account(f"{slug}-member")
    member.email_verified_at = timezone.now()
    member.save(update_fields=["email_verified_at"])
    event = open_event(space)
    return space, staff, member, event, register(event, member=member, actor=member)


def test_staff_removal_is_announced_only_after_the_undo_window():
    _space, staff, member, _event, row = registered()
    cancel_registration(row, actor=staff)
    envelope = NotificationEnvelope.objects.get(source_kind="events.removal", recipient=member)
    row.refresh_from_db()
    assert envelope.available_at >= row.cancelled_at + timedelta(minutes=5)
    assert envelope.timing_policy == "deferred" and removal_eligible(envelope)
    # Undo inside the window: the deferred notice no longer matches and never sends.
    EventRegistration.objects.filter(pk=row.pk).update(status="registered", cancelled_at=None)
    assert not removal_eligible(envelope)


def test_member_cancel_keeps_the_ordinary_notice():
    _space, _staff, member, _event, row = registered("selfcancel")
    cancel_registration(row, actor=member, member_cancel=True)
    assert not NotificationEnvelope.objects.filter(source_kind="events.removal").exists()


def test_new_verified_email_resends_the_ticket_once_per_address():
    _space, _staff, member, _event, _row = registered("resend")
    assert resend_tickets(member) == 0  # same address as at registration
    type(member).objects.filter(pk=member.pk).update(email="moved@example.test")
    member.refresh_from_db()
    assert resend_tickets(member) == 1
    resend_tickets(member)
    assert NotificationEnvelope.objects.filter(source_kind="events.ticket_resend").count() == 1


def test_verification_audit_row_triggers_the_resend(django_capture_on_commit_callbacks):
    _space, _staff, member, _event, _row = registered("verify")
    type(member).objects.filter(pk=member.pk).update(email="fresh@example.test")
    with django_capture_on_commit_callbacks(execute=True):
        record(member, "member.email_verified", target=member, meta={})
    assert NotificationEnvelope.objects.filter(source_kind="events.ticket_resend", recipient=member).exists()


def test_day_ahead_reminder_skips_sign_ups_from_the_last_twelve_hours():
    now = timezone.now()
    fresh = SimpleNamespace(created_at=now - timedelta(hours=2))
    settled = SimpleNamespace(created_at=now - timedelta(hours=13))
    assert fresh_signup(fresh, -24 * 3600, now)
    assert not fresh_signup(settled, -24 * 3600, now)
    assert not fresh_signup(fresh, -2 * 3600, now)  # short-lead reminders still go


def test_confirmation_carries_the_join_link_only_for_confirmed_online_registrants(monkeypatch):
    rendered = {"subject": "You are in", "text": "See you", "html": "<p>See you</p>"}
    row = SimpleNamespace()
    monkeypatch.setattr("apps.events.online_delivery.join_url_for", lambda registration: "https://meet.example/x")
    out = with_join_url(rendered, "registration_created", row)
    assert "Join online: https://meet.example/x" in out["text"] and "meet.example" in out["html"]
    assert with_join_url(rendered, "registration_cancelled", row) == rendered
    monkeypatch.setattr("apps.events.online_delivery.join_url_for", lambda registration: None)
    assert with_join_url(rendered, "registration_created", row) == rendered

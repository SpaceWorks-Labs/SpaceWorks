"""Booking notices become explicit personal envelopes; rooms keep the staff summary only."""
import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.integrations.notification_sources import source_eligible

from .helpers import client_for, envelopes, world

pytestmark = pytest.mark.django_db


def test_new_makerspaces_notify_requesters_by_default():
    from apps.makerspaces.models import Makerspace
    assert Makerspace.objects.create(name="Fresh", slug="p2n-fresh").booking_requester_notifications_enabled is True


def test_created_and_confirmed_reach_owner_staff_and_grant_holders():
    w = world("p2n-a")
    created = envelopes(makerspace=w.tenant, event="created")
    assert created.filter(audience="requester", recipient=w.member).count() == 1
    assert created.filter(audience="staff", recipient=w.manager).count() == 1
    grant = created.get(recipient=w.grantee)
    assert (grant.audience, grant.source_kind) == ("member", "bookings.grant_alert")
    client_for(w.manager).post(reverse("admin-booking-approve", kwargs={"pk": w.booking.pk}), {}, format="json")
    confirmed = envelopes(makerspace=w.tenant, event="confirmed", audience="requester").get()
    assert confirmed.recipient_id == w.member.pk and source_eligible(confirmed)
    # The earlier "created" notice is now stale: its revision no longer matches.
    assert not source_eligible(created.get(audience="requester"))


def test_reject_reason_reaches_the_owner_envelope_body():
    w = world("p2n-b")
    response = client_for(w.manager).post(reverse("admin-booking-reject", kwargs={"pk": w.booking.pk}),
                               {"reason": "Closed for a private event"}, format="json")
    assert response.status_code == 200, response.data
    owner = envelopes(makerspace=w.tenant, event="rejected", audience="requester").get()
    assert "Closed for a private event" in json.loads(owner.message_body)["text"]
    from apps.bookings.notifications import scope_for
    from apps.integrations.staff_notifications import staff_user_ids_for_feature
    # The room bridge also retains a recipient-less legacy.lifecycle shell;
    # only the lifecycle source represents personal staff recipients.
    staff = envelopes(makerspace=w.tenant, event="rejected", audience="staff", source_kind="bookings.lifecycle")
    assert not envelopes(makerspace=w.tenant, event="rejected", source_kind="legacy.lifecycle",
                         recipient_id__isnull=False).exists()
    expected_ids = set(staff_user_ids_for_feature(w.tenant, "bookings", event="rejected",
                                                scope=scope_for(w.booking, "rejected"))) - {w.member.pk}
    assert set(staff.values_list("recipient_id", flat=True)) == expected_ids
    manager = staff.get(recipient=w.manager)
    manager_content = json.loads(manager.message_body)
    assert "/admin/bookings" in manager_content["link"]
    assert "Closed for a private event" in manager_content["text"]
    for notice in staff:
        assert source_eligible(notice)
        content = json.loads(notice.message_body)
        assert content == manager_content
        assert "/admin/bookings" in content["link"]


def test_toggle_off_suppresses_owner_envelopes_and_live_check():
    w = world("p2n-c")
    owner = envelopes(makerspace=w.tenant, event="created", audience="requester").get()
    w.space.requester_notifications_enabled = False
    w.space.save(update_fields=["requester_notifications_enabled"])
    assert not source_eligible(owner)
    client_for(w.manager).post(reverse("admin-booking-approve", kwargs={"pk": w.booking.pk}), {}, format="json")
    assert not envelopes(makerspace=w.tenant, event="confirmed", audience="requester").exists()
    assert envelopes(makerspace=w.tenant, event="confirmed", audience="staff").exists()


def test_revoked_grant_fails_the_live_grant_check():
    w = world("p2n-d")
    grant_envelope = envelopes(makerspace=w.tenant, event="created", recipient=w.grantee).get()
    assert source_eligible(grant_envelope)
    w.grant.revoked_at = timezone.now()
    w.grant.save(update_fields=["revoked_at"])
    assert not source_eligible(grant_envelope)


def test_reminder_is_a_personal_envelope(monkeypatch):
    from apps.bookings import reminders
    from apps.operations.models import ReminderSchedule
    w = world("p2n-e", approval="instant", start_in=timedelta(hours=3))
    schedule = ReminderSchedule.objects.create(
        makerspace=w.tenant, source="bookings.booking", subject=reminders.identity(w.booking), kind="starts",
        offset_seconds=-3600, due_at=w.booking.starts_at, remind_at=w.booking.starts_at - timedelta(hours=1))
    monkeypatch.setattr(reminders, "_eligible", lambda *args: w.booking)
    monkeypatch.setattr(reminders, "notification_account", lambda *args: w.member)
    result = reminders.dispatch_booking_reminder(w.tenant, schedule, None, timezone.now(), None)
    assert result.delivered_counts
    envelope = envelopes(makerspace=w.tenant, event="reminder").get()
    assert envelope.recipient_id == w.member.pk and envelope.source_kind == "bookings.reminder"

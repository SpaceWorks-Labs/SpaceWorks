"""Events notification-coverage rows become source-backed envelopes through the outbox."""
from tests.events.manual_grant_fixture import create_manual_grant

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.events import notifications, services
from apps.events.models import EventStaffGrant
from apps.integrations.notification_sources import source_eligible
from apps.makerspaces.models import MakerspaceMembership
from tests.p2_events.helpers import account, envelopes, event, make_member, make_staff, registration, space

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_delivery(monkeypatch):
    # Intent is what these rows assert; the shared delivery engine has its own suite.
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)


def test_registration_created_emits_separate_staff_and_owner_envelopes():
    home = space("ad-created")
    staff, owner = make_staff(home), account("ad-owner")
    row = event(home)
    created = services.register(row, member=owner, actor=staff, staff_registration=True)
    staff_rows = envelopes(event="registration_created", audience="staff")
    owner_rows = envelopes(event="registration_created", audience="requester")
    assert [e.recipient_id for e in staff_rows] == [staff.pk]
    assert [e.recipient_id for e in owner_rows] == [owner.pk]
    staff_env, owner_env = staff_rows.get(), owner_rows.get()
    assert staff_env.source_kind == owner_env.source_kind == "events.lifecycle"
    assert staff_env.message_body != owner_env.message_body  # separate bodies per audience
    # The addressed-messaging projection adds reviewed scalar template variables
    # (event.id, event.when, makerspace.name, ...) on top of the source identity.
    assert {"event_id": row.pk, "registration_id": created.pk, "event_status": "published",
            "notice": "registration_created"}.items() <= owner_env.context.items()
    assert set(staff_env.deliveries.values_list("channel", "state")) == {("in_app", "skipped"), ("native_push", "skipped")}
    assert not owner_env.deliveries.exists()
    assert source_eligible(owner_env) and source_eligible(staff_env)


def test_owner_envelope_stops_being_eligible_when_ownership_changes():
    home = space("ad-owner-live")
    staff, owner = make_staff(home), account("ad-live")
    created = services.register(event(home), member=owner, actor=staff, staff_registration=True)
    owner_env = envelopes(audience="requester").get()
    created.member = account("ad-other")
    created.save(update_fields=["member"])
    assert not source_eligible(owner_env)


def test_rollback_emits_nothing():
    home = space("ad-rollback")
    staff, owner = make_staff(home), account("ad-rb")
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            services.register(event(home), member=owner, actor=staff, staff_registration=True)
            raise RuntimeError("rollback")
    assert not envelopes().exists()


def test_event_cancellation_fans_out_to_live_registration_owners_once():
    home = space("ad-cancel")
    staff = make_staff(home)
    row = event(home)
    keep, wait, gone = account("ad-k"), account("ad-w"), account("ad-g")
    registration(row, keep)
    registration(row, wait, status="waitlisted")
    registration(row, gone, status="cancelled")
    services.cancel(row, actor=staff)
    owners = set(envelopes(event="cancelled", audience="requester").values_list("recipient_id", flat=True))
    assert owners == {keep.pk, wait.pk}
    assert envelopes(event="cancelled", audience="staff", recipient=staff).exists()


def test_event_staff_grant_holders_get_registration_notices_and_lose_them_on_revoke():
    home = space("ad-grant")
    staff, desk, owner = make_staff(home), account("ad-desk"), account("ad-g-owner")
    row = event(home)
    grant = create_manual_grant(makerspace=home, event=row, user=desk,
                                           permissions=["manage_registrations"], granted_by=staff)
    services.register(row, member=owner, actor=staff, staff_registration=True)
    delegate = envelopes(source_kind="events.grant_staff").get()
    assert delegate.recipient_id == desk.pk and source_eligible(delegate)
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["revoked_at"])
    assert not source_eligible(delegate)


def test_revoked_member_owner_gets_no_envelope_but_account_only_owner_does():
    home = space("ad-revoked")
    staff = make_staff(home)
    row = event(home)
    member = make_member(home, "ad-rev")
    MakerspaceMembership.objects.filter(user=member, makerspace=home).update(status="revoked")
    revoked_reg = registration(row, member)
    notifications.notify_event_lifecycle(row, "registration_approved", revoked_reg.pk)
    assert not envelopes(audience="requester", recipient=member).exists()
    guest = account("ad-guest")
    guest_reg = registration(row, guest)
    notifications.notify_event_lifecycle(row, "registration_approved", guest_reg.pk)
    assert envelopes(audience="requester", recipient=guest, event="registration_approved").exists()


def test_reminder_dispatch_emits_owner_envelope_bound_to_the_start_time():
    from apps.events.reminders import dispatch_event_reminder
    from apps.makerspaces.reminder_policy import reminder_offsets
    home = space("ad-reminder")
    guest = account("ad-rem")
    row = event(home, days=0)
    row.starts_at = timezone.now() + timedelta(hours=2)
    row.ends_at = row.starts_at + timedelta(hours=1)
    row.save(update_fields=["starts_at", "ends_at"])
    reg = registration(row, guest)
    offsets = reminder_offsets(home, "event") or [-3600]
    schedule = SimpleNamespace(pk=991, kind="starts", offset_seconds=offsets[0], due_at=row.starts_at,
                               subject=f"{reg.pk}:{row.starts_at.isoformat()}")
    from unittest import mock
    with mock.patch("apps.events.reminders.reminder_offsets", return_value=[schedule.offset_seconds]):
        result = dispatch_event_reminder(home, schedule, None, timezone.now(), None)
    assert result.scheduled and result.delivered_counts
    reminder = envelopes(source_kind="events.reminder").get()
    assert reminder.recipient_id == guest.pk and reminder.audience == "requester" and source_eligible(reminder)
    row.starts_at += timedelta(hours=1)
    row.ends_at += timedelta(hours=1)
    row.save(update_fields=["starts_at", "ends_at"])
    assert not source_eligible(reminder)


def test_broadcast_channel_fanout_skips_email_and_rechecks_the_campaign(monkeypatch):
    from apps.events.broadcast_channels import event_broadcast_channels
    from apps.events.models_broadcasts import EventBroadcast
    home = space("ad-broadcast")
    home.enabled_modules = sorted(set(home.enabled_modules) | {"notifications", "email"})
    home.enabled_features = sorted(set(home.enabled_features) | {"events.broadcasts"})
    home.save(update_fields=["enabled_modules", "enabled_features"])
    staff, guest = make_staff(home), account("ad-bc")
    row = event(home)
    registration(row, guest)
    campaign = EventBroadcast.objects.create(makerspace=home, event=row, created_by=staff, subject="Hi",
                                             body="Doors open at 6", status="queued", statuses=["registered"])
    assert event_broadcast_channels(campaign.pk) == 1
    envelope = envelopes(source_kind="events.broadcast").get()
    assert envelope.recipient_id == guest.pk
    assert list(envelope.deliveries.values_list("channel", "state")) == [("email", "skipped")]
    assert source_eligible(envelope)
    campaign.status = "cancelled"
    campaign.save(update_fields=["status"])
    assert not source_eligible(envelope)

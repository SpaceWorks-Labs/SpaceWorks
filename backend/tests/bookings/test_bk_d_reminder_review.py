"""Upgrade claim fences and independent requester reminder channels."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.reminder_delivery import identity
from apps.bookings.services_bookings import approve_booking
from apps.integrations.models import EmailLog, NotificationPreference
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.models_inbox import MemberNotificationPreference, NotificationInboxRow
from apps.operations.models import ReminderSchedule
from apps.operations.reminder_members import occurrence_subject
from apps.operations.reminder_services import claim_reminders, complete_reminder, schedule_reminders
from tests.bookings.bk_d_reminder_helpers import sweep_and_deliver as run_reminder_sweep
from apps.integrations.models_contract import NotificationEnvelope
from tests.bookings.bk_d_helpers import fixture, reserve, smtp
from tests.bookings.bk_d_reminder_helpers import cancel, move

pytestmark = pytest.mark.django_db(transaction=True)
SOURCE = "bookings.booking"


def _world(monkeypatch, *, approved=False):
    now = timezone.now()
    clock = [now]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    monkeypatch.setattr("apps.bookings.notifications.notify_booking_status", lambda *args, **kwargs: None)
    tenant, manager, _, resource, _, owner, booking = fixture(monkeypatch)
    if approved:
        cancel(booking, owner)
        resource.approval_mode = BookableSpace.ApprovalMode.APPROVE
        resource.save(update_fields=["approval_mode"])
        booking = reserve(resource, owner, booking.starts_at)
        assert booking.status == Booking.Status.PENDING
        booking = approve_booking(booking, actor=manager)
        assert booking.calendar_sequence == 1
    return tenant, owner, booking, clock, smtp(monkeypatch)


def _legacy_claim(tenant, booking, now, state):
    schedule, = schedule_reminders(
        makerspace=tenant, source=SOURCE,
        subject=occurrence_subject(booking.pk, booking.starts_at), kind="starts",
        due_at=booking.starts_at, offsets=(-86400,),
    )
    claim, = claim_reminders(makerspace=tenant, source=SOURCE, now=now)
    assert claim.pk == schedule.pk
    if state != ReminderSchedule.State.CLAIMED:
        assert complete_reminder(
            makerspace=tenant, reminder_id=claim.pk, claim_token=claim.claim_token,
            now=now, failed=state == ReminderSchedule.State.FAILED,
        )
    claim.refresh_from_db()
    assert claim.state == state
    return claim


@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("state", ["completed", "claimed", "failed"])
def test_legacy_claim_fences_unchanged_booking_at_existing_revision(monkeypatch, approved, state):
    tenant, owner, booking, clock, send = _world(monkeypatch, approved=approved)
    legacy = _legacy_claim(tenant, booking, clock[0], state)
    for _ in range(2):
        assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE]) == {
            "dispatched": 0, "skipped": 0, "failed": 0,
        }
    assert not send.called
    assert not EmailLog.objects.filter(makerspace=tenant, event="reminder").exists()
    assert list(ReminderSchedule.objects.filter(makerspace=tenant).values_list("pk", flat=True)) == [legacy.pk]
    legacy.refresh_from_db()
    assert legacy.state == state


@pytest.mark.parametrize("state", ["completed", "claimed", "failed"])
def test_later_offset_cannot_redispatch_an_earlier_legacy_claim(monkeypatch, state):
    tenant, owner, booking, clock, send = _world(monkeypatch, approved=True)
    tenant.booking_reminder_lead_hours = [24, 2]
    tenant.save(update_fields=["booking_reminder_lead_hours"])
    legacy = _legacy_claim(tenant, booking, clock[0], state)
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 0
    clock[0] = booking.starts_at - timedelta(hours=1)
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    assert send.call_count == 1
    logs = NotificationEnvelope.objects.filter(makerspace=tenant, source_kind="bookings.reminder")
    assert logs.count() == 1 and logs.get().context["offset_seconds"] == -7200
    assert logs.get().deliveries.get(channel="email").state == "sent"
    legacy.refresh_from_db()
    assert legacy.state == state
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 0
    assert send.call_count == 1


@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("replacement", [False, True])
@pytest.mark.parametrize("limit", [1, 200])
def test_pending_legacy_later_step_survives_identity_upgrade(monkeypatch, approved, replacement, limit):
    tenant, owner, booking, clock, send = _world(monkeypatch, approved=approved)
    tenant.booking_reminder_lead_hours = [24, 2]
    tenant.save(update_fields=["booking_reminder_lead_hours"])
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    assert send.call_count == 1
    earlier = ReminderSchedule.objects.get(makerspace=tenant, source=SOURCE, offset_seconds=-86400)
    pending = ReminderSchedule.objects.get(makerspace=tenant, source=SOURCE, offset_seconds=-7200)
    # Re-express a real delivery and its still-pending later step as pre-upgrade
    # identities, retaining the committed token/state rather than faking a send.
    ReminderSchedule.objects.filter(pk__in=[earlier.pk, pending.pk]).update(
        subject=occurrence_subject(booking.pk, booking.starts_at),
    )
    send.reset_mock()
    if replacement:
        # Discovery may already have seeded new identities before the upgrade.
        schedule_reminders(makerspace=tenant, source=SOURCE, subject=identity(booking),
                           kind="starts", due_at=booking.starts_at, offsets=(-86400, -7200))
    clock[0] = booking.starts_at - timedelta(hours=1)
    results = [run_reminder_sweep(now=clock[0], limit=limit, source_keys=[SOURCE]) for _ in range(3)]
    assert sum(result["dispatched"] for result in results) == 1
    assert sum(result["failed"] for result in results) == 0
    assert send.call_count == 1
    log = NotificationEnvelope.objects.get(makerspace=tenant, source_kind="bookings.reminder", context__offset_seconds=-7200)
    assert log.deliveries.get(channel="email").state == "sent" and log.context["offset_seconds"] == -7200
    assert log.revision == str(booking.calendar_sequence)
    assert not ReminderSchedule.objects.filter(pk=pending.pk).exists()
    assert ReminderSchedule.objects.get(
        makerspace=tenant, source=SOURCE, subject=identity(booking), offset_seconds=-7200,
    ).state == "completed"
    earlier.refresh_from_db()
    assert earlier.state == "completed" and earlier.subject == occurrence_subject(booking.pk, booking.starts_at)


@pytest.mark.parametrize("approved", [False, True])
def test_upgrade_preserves_both_due_and_future_pending_legacy_steps(monkeypatch, approved):
    tenant, owner, booking, clock, send = _world(monkeypatch, approved=approved)
    tenant.booking_reminder_lead_hours = [24, 2]
    tenant.save(update_fields=["booking_reminder_lead_hours"])
    legacy = schedule_reminders(
        makerspace=tenant, source=SOURCE,
        subject=occurrence_subject(booking.pk, booking.starts_at), kind="starts",
        due_at=booking.starts_at, offsets=(-86400, -7200),
    )
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    assert not ReminderSchedule.objects.filter(pk__in=[step.pk for step in legacy]).exists()
    future = ReminderSchedule.objects.get(makerspace=tenant, source=SOURCE, offset_seconds=-7200)
    assert future.subject == identity(booking) and future.state == "pending"
    assert future.remind_at == booking.starts_at - timedelta(hours=2)
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 0
    clock[0] = booking.starts_at - timedelta(hours=1)
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 0
    assert send.call_count == 2
    assert set(NotificationEnvelope.objects.filter(makerspace=tenant, source_kind="bookings.reminder").values_list(
        "context__offset_seconds", flat=True,
    )) == {-86400, -7200}


def test_pending_legacy_duplicate_keeps_already_delivered_replacement_closed(monkeypatch):
    tenant, owner, booking, clock, send = _world(monkeypatch)
    tenant.booking_reminder_lead_hours = [24, 2]
    tenant.save(update_fields=["booking_reminder_lead_hours"])
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    delivered = ReminderSchedule.objects.get(makerspace=tenant, source=SOURCE, offset_seconds=-86400)
    token, completed_at = delivered.claim_token, delivered.completed_at
    schedule_reminders(
        makerspace=tenant, source=SOURCE,
        subject=occurrence_subject(booking.pk, booking.starts_at), kind="starts",
        due_at=booking.starts_at, offsets=(-86400, -7200),
    )
    clock[0] = booking.starts_at - timedelta(hours=1)
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 0
    assert send.call_count == 2
    delivered.refresh_from_db()
    assert (delivered.state, delivered.claim_token, delivered.completed_at) == ("completed", token, completed_at)
    assert ReminderSchedule.objects.filter(makerspace=tenant, source=SOURCE).count() == 2


def test_legacy_claim_does_not_fence_a_moved_start(monkeypatch):
    tenant, owner, booking, clock, send = _world(monkeypatch, approved=True)
    _legacy_claim(tenant, booking, clock[0], "completed")
    moved = move(booking, owner)
    assert moved.starts_at != booking.starts_at
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    log = NotificationEnvelope.objects.get(makerspace=tenant, source_kind="bookings.reminder")
    assert log.revision == str(moved.calendar_sequence)
    assert send.call_count == 1


def _inbox_enabled(tenant):
    tenant.enabled_features += ["notifications.member_inbox", "notifications.member_preferences"]
    tenant.save(update_fields=["enabled_features"])
    for channel in ("email", "in_app"):
        NotificationPreference.objects.update_or_create(
            makerspace=tenant, feature="bookings", channel=channel, defaults={"enabled": True},
        )


@pytest.mark.parametrize("email_gate", ["preference", "matrix", "module", "unverified", "missing_email"])
def test_email_only_gate_preserves_independently_enabled_reminder_inbox(monkeypatch, email_gate):
    tenant, owner, booking, clock, send = _world(monkeypatch)
    _inbox_enabled(tenant)
    if email_gate == "preference":
        MemberNotificationPreference.objects.create(
            makerspace=tenant, user=owner, feature="bookings", channel="email", enabled=False,
        )
    elif email_gate == "matrix":
        NotificationPreference.objects.filter(makerspace=tenant, feature="bookings", channel="email").update(enabled=False)
    elif email_gate == "module":
        tenant.enabled_modules.remove("email")
        tenant.save(update_fields=["enabled_modules"])
    elif email_gate == "unverified":
        # The old same-owner booking contact exception cannot prove a different mailbox.
        User.objects.filter(pk=owner.pk).update(email="unproven@example.test", email_verified_at=None)
    else:
        User.objects.filter(pk=owner.pk).update(email="")
    for _ in range(2):
        result = run_reminder_sweep(now=clock[0], source_keys=[SOURCE])
        assert result["failed"] == 0
    inbox = NotificationInboxRow.objects.get(makerspace=tenant, event="reminder")
    assert (inbox.user_id, inbox.feature, inbox.event) == (owner.pk, "bookings", "reminder")
    assert not send.called
    assert not EmailLog.objects.filter(makerspace=tenant, event="reminder", status="sent").exists()
    assert ReminderSchedule.objects.get(makerspace=tenant).state == "completed"


@pytest.mark.parametrize("gate", ["preference", "matrix", "feature", "requester", "account", "membership"])
def test_independent_inbox_and_owner_gates_still_apply(monkeypatch, gate):
    tenant, owner, booking, clock, send = _world(monkeypatch)
    _inbox_enabled(tenant)
    if gate == "preference":
        MemberNotificationPreference.objects.create(
            makerspace=tenant, user=owner, feature="bookings", channel="in_app", enabled=False,
        )
    elif gate == "matrix":
        NotificationPreference.objects.filter(makerspace=tenant, feature="bookings", channel="in_app").update(enabled=False)
    elif gate == "feature":
        tenant.enabled_features.remove("notifications.member_inbox")
        tenant.save(update_fields=["enabled_features"])
    elif gate == "requester":
        booking.space.requester_notifications_enabled = False
        booking.space.save(update_fields=["requester_notifications_enabled"])
    elif gate == "account":
        User.objects.filter(pk=owner.pk).update(is_active=False)
    else:
        MakerspaceMembership.objects.create(makerspace=tenant, user=owner, receives_notifications=False, role="custom", assigned_role=tenant.roles.get(slug="member"))
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["failed"] == 0
    assert not NotificationInboxRow.objects.filter(makerspace=tenant, event="reminder").exists()
    assert send.call_count == (1 if gate in {"preference", "matrix", "feature"} else 0)

from datetime import timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.db import transaction
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.notifications_p2_requests import notify_request
from apps.hardware_requests.notifications_p2_reminders import deliver
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.integrations.notification_tasks import deliver_envelope
from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy

pytestmark = pytest.mark.django_db


def loan(world, status="accepted"):
    return HardwareRequest.objects.create(makerspace=world.space, requester=world.owner,
        requester_username=world.owner.username, requester_contact_email=world.owner.email,
        requester_contact_verified=True, status=status, accepted_by=world.manager,
        issued_by=world.manager, return_due_at=timezone.now() - timedelta(hours=1))


@pytest.mark.parametrize("event,status", [
    ("submitted", "pending_approval"), ("accepted", "accepted"), ("rejected", "rejected"),
    ("issued", "issued"), ("partially_returned", "partially_returned"),
    ("returned", "returned"), ("closed_with_issue", "closed_with_issue"),
])
def test_hardware_coverage_owner_staff_separate(equipment, event, status):
    row = loan(equipment, status)
    result = notify_request(row, event)
    assert result.scheduled
    rows = NotificationEnvelope.objects.filter(source_kind="hardware.request", source_id=str(row.pk))
    assert set(rows.values_list("recipient_id", "audience")) == {
        (equipment.owner.pk, "requester"), (equipment.manager.pk, "staff")}
    own = rows.get(audience="requester")
    assert own.stream == "hardware" and own.event == event
    assert own.mandatory == (event == "closed_with_issue")
    assert "telegram" in {target.channel for target in resolve(own)}
    deliver_envelope(own.pk)
    assert equipment.fake.calls
    assert str(row.public_token) not in str(equipment.fake.calls)
    assert equipment.owner.email not in str(own.context)
    notify_request(row, event)
    assert rows.count() == 2


def test_domain_rollback_removes_intents(equipment):
    row = loan(equipment)
    with pytest.raises(RuntimeError), transaction.atomic():
        notify_request(row, "accepted")
        assert NotificationEnvelope.objects.exists()
        raise RuntimeError("rollback")
    assert not NotificationEnvelope.objects.exists()


def test_owner_change_and_revision_cancel_old_notice(equipment):
    row = loan(equipment)
    notify_request(row, "accepted")
    envelope = NotificationEnvelope.objects.get(audience="requester")
    row.requester = equipment.manager
    row.save(update_fields=["requester", "updated_at"])
    assert not source_eligible(envelope)


def test_legacy_return_reminder_keeps_email_and_chat(equipment, monkeypatch):
    row = loan(equipment, "issued")
    notify_request(row, "return_reminder")
    envelope = NotificationEnvelope.objects.get(audience="requester")
    # This is one of the five mail-module exemptions, even with email disabled.
    monkeypatch.setattr("apps.makerspaces.platform.module_enabled", lambda space, key: key != "email")
    assert envelope.mandatory and envelope.timing_policy == "immediate"
    assert {target.channel for target in resolve(envelope)} == {"email", "telegram"}
    deliver_envelope(envelope.pk)
    assert equipment.fake.calls and equipment.sent[0][0] == "email"


def test_mandatory_email_still_obeys_suppression(equipment):
    from apps.integrations.models_suppression import EmailSuppression
    from apps.integrations.email_preferences import address_hash
    row = loan(equipment, "issued")
    notify_request(row, "return_reminder")
    envelope = NotificationEnvelope.objects.get(audience="requester")
    EmailSuppression.objects.create(makerspace=equipment.space,
        address_hash=address_hash(equipment.space.pk, equipment.owner.email), reason="bounce")
    assert {target.channel for target in resolve(envelope)} == {"telegram"}


def test_legacy_email_mute_keeps_independently_selected_chat(equipment):
    from apps.integrations.models import EmailNotificationMute
    row = loan(equipment)
    EmailNotificationMute.objects.create(makerspace=equipment.space, stream="hardware",
        audience="requester", target="requester", event="request_accepted")
    notify_request(row, "accepted")
    envelope = NotificationEnvelope.objects.get(audience="requester")
    assert {target.channel for target in resolve(envelope)} == {"telegram"}


@pytest.mark.parametrize("kind,offset,event", [
    ("borrower", -3600, "return_reminder"), ("borrower", 0, "return_reminder"),
    ("borrower", 3600, "return_reminder"), ("escalation", 86400, "overdue_escalated"),
])
def test_loan_ladder_coverage(equipment, kind, offset, event):
    MakerspaceLoanPolicy.objects.create(makerspace=equipment.space,
        loan_reminder_offsets_hours=[-1, 0, 1], loan_escalate_overdue_days=1)
    row = loan(equipment, "issued")
    reminder = SimpleNamespace(kind=kind, offset_seconds=offset)
    message = SimpleNamespace(body="Return by the recorded due time.")
    result = deliver(equipment.space, row, reminder, message, ZoneInfo("UTC"))
    assert result.scheduled
    envelopes = NotificationEnvelope.objects.filter(source_kind="hardware.loan_reminder")
    assert set(envelopes.values_list("event", flat=True)) == {event}
    if kind == "borrower":
        assert list(envelopes.values_list("recipient_id", "audience", "mandatory")) == [(equipment.owner.pk, "requester", True)]
        assert {t.channel for t in resolve(envelopes.get())} == {"telegram", "email"}
    else:
        assert set(envelopes.values_list("audience", flat=True)) == {"staff"}
    row.status = "returned"
    row.save(update_fields=["status", "updated_at"])
    assert all(not source_eligible(envelope) for envelope in envelopes)


@pytest.mark.parametrize("ladder", [False, True])
def test_unverified_owner_mailbox_keeps_mandatory_reminder_email(equipment, ladder):
    """A same-owner contact proof reaches mandatory mail through one envelope leg."""
    from apps.integrations.models import EmailLog
    equipment.owner.email_verified_at = None
    equipment.owner.save(update_fields=["email_verified_at"])
    row = loan(equipment, "issued")
    if ladder:
        MakerspaceLoanPolicy.objects.create(makerspace=equipment.space,
            loan_reminder_offsets_hours=[0], loan_escalate_overdue_days=1)
        deliver(equipment.space, row, SimpleNamespace(kind="borrower", offset_seconds=0),
                SimpleNamespace(body="Return by the recorded due time."), ZoneInfo("UTC"))
    else:
        notify_request(row, "return_reminder")
    envelope = NotificationEnvelope.objects.get(audience="requester")
    assert {target.channel for target in resolve(envelope)} == {"telegram", "email"}
    assert envelope.recipient.email == row.requester_contact_email == equipment.owner.email
    assert envelope.event == "return_reminder"
    assert not EmailLog.objects.filter(source_kind="hardware.owner_mailbox").exists()
    deliver_envelope(envelope.pk)
    assert envelope.deliveries.filter(channel="email", state="sent").count() == 1
    if not ladder:
        notify_request(row, "return_reminder")
        deliver_envelope(envelope.pk)
        assert envelope.deliveries.filter(channel="email").count() == 1
    # A changed address loses the snapshot proof; fresh account verification restores it.
    equipment.owner.email = "changed-p2-owner@example.test"
    equipment.owner.save(update_fields=["email"])
    assert {target.channel for target in resolve(envelope)} == {"telegram"}
    equipment.owner.email_verified_at = timezone.now()
    equipment.owner.save(update_fields=["email_verified_at"])
    assert {target.channel for target in resolve(envelope)} == {"telegram", "email"}


def test_verified_owner_mailbox_has_no_direct_duplicate(equipment):
    from apps.integrations.models import EmailLog
    row = loan(equipment, "issued")
    notify_request(row, "return_reminder")
    assert not EmailLog.objects.filter(source_kind="hardware.owner_mailbox").exists()


def test_unverified_owner_lifecycle_mail_respects_preference(equipment):
    from apps.integrations.models import EmailLog
    from apps.notifications.models_preferences import NotificationPreference
    equipment.owner.email_verified_at = None
    equipment.owner.save(update_fields=["email_verified_at"])
    row = loan(equipment)
    notify_request(row, "accepted")  # owner selected Telegram only in the fixture
    assert not EmailLog.objects.filter(source_kind="hardware.owner_mailbox").exists()
    NotificationPreference.objects.filter(user=equipment.owner, category="hardware_requests").update(
        channels=["telegram", "email"])
    row.save(update_fields=["updated_at"])
    notify_request(row, "accepted")
    envelope = NotificationEnvelope.objects.filter(audience="requester", event="accepted").latest("pk")
    assert {target.channel for target in resolve(envelope)} == {"telegram", "email"}
    assert not EmailLog.objects.filter(source_kind="hardware.owner_mailbox").exists()
    deliver_envelope(envelope.pk)
    assert envelope.deliveries.filter(channel="email", state="sent").count() == 1


def test_failed_notification_query_cannot_poison_domain_transaction(equipment, monkeypatch):
    from django.db import connection

    def broken(**kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM p2_table_that_does_not_exist")

    monkeypatch.setattr("apps.hardware_requests.notifications_p2.emit", broken)
    row = loan(equipment)
    with transaction.atomic():
        assert notify_request(row, "accepted") is None
        # The workflow's own transaction is still usable afterwards.
        assert HardwareRequest.objects.filter(pk=row.pk).exists()

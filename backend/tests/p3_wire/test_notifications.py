from unittest.mock import Mock
from uuid import NAMESPACE_URL, uuid5

import pytest
from django.db import transaction
from django.utils import timezone

from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_builtin import send_builtin
from apps.notifications.emit import emit_notification
from apps.notifications.models_inbox import NotificationInboxRow
from apps.operations.models import StocktakeSession
from apps.operations.notifications_p2_alerts import email_failure_intent, notify_stocktake, stocktake_intent

pytestmark = pytest.mark.django_db


def test_member_broadcast_emits_owned_envelopes_instead_of_legacy_mail(world):
    from apps.notifications.broadcasts import send_broadcast
    from apps.integrations.notification_resolution import resolve
    row, count = send_broadcast(world.space, actor=world.staff, title="Member news", body="The lab is open.")
    envelopes = NotificationEnvelope.objects.filter(source_kind="membership.broadcast", source_id=str(row.pk))
    assert envelopes.count() == count
    # A member broadcast reaches community-track members only; the staff person holds a staff-track row.
    assert set(envelopes.values_list("recipient_id", flat=True)) == {world.owner.pk, world.other.pk}
    assert not EmailLog.objects.filter(event="broadcast").exists()
    envelope = envelopes.get(recipient=world.owner)
    world.owner.makerspace_memberships.filter(makerspace=world.space).update(receives_notifications=False)
    assert resolve(envelope) == []


def test_member_broadcast_is_rolled_back_with_domain_transaction(world):
    from apps.notifications.broadcasts import send_broadcast
    from apps.notifications.models_broadcasts import MemberBroadcast
    with pytest.raises(RuntimeError), transaction.atomic():
        send_broadcast(world.space, actor=world.staff, title="News", body="Rollback")
        raise RuntimeError("rollback")
    assert not MemberBroadcast.objects.filter(makerspace=world.space).exists()
    assert not NotificationEnvelope.objects.filter(source_kind="membership.broadcast").exists()


@pytest.mark.parametrize("event", ["scheduled", "completed"])
@pytest.mark.parametrize("legacy_first", [True, False])
def test_stocktake_legacy_mirror_and_envelope_share_one_inbox_identity(world, event, legacy_first, monkeypatch,
                                                                    django_capture_on_commit_callbacks):
    from types import SimpleNamespace
    monkeypatch.setattr("apps.notifications.inbox._hint", lambda *_: None)
    monkeypatch.setattr("apps.notifications.legacy_inbox._hint", lambda *_: None)
    row = StocktakeSession.objects.create(makerspace=world.space,
        status="completed" if event == "completed" else "counting",
        completed_at=timezone.now() if event == "completed" else None)
    notify_stocktake(row, event)
    envelope = NotificationEnvelope.objects.get(makerspace=world.space, recipient=world.staff,
        source_kind="operations.stocktake", source_id=str(row.pk), event=event)
    def legacy():
        with django_capture_on_commit_callbacks(execute=True):
            emit_notification(world.space, title="Stocktake", event=f"stocktake.{event}",
                              source_intent=stocktake_intent(row, event))
    def personal():
        send_builtin(SimpleNamespace(channel="in_app", envelope=envelope), {"subject": "Stocktake", "text": "Review"})
    (legacy if legacy_first else personal)()
    (personal if legacy_first else legacy)()
    rows = NotificationInboxRow.objects.filter(makerspace=world.space, user=world.staff)
    assert rows.count() == 1
    assert rows.get().event_key == uuid5(NAMESPACE_URL, envelope.dedup_key)


def test_first_email_failure_passes_source_identity_matching_its_envelope(world, monkeypatch):
    from apps.integrations.dispatch import _deliver
    def fail(*args, **kwargs):
        raise RuntimeError("SMTP unavailable")
    monkeypatch.setattr("apps.integrations.email.makerspace_mail_connection", fail)
    legacy = Mock()
    monkeypatch.setattr("apps.notifications.emit.emit_notification", legacy)
    log = EmailLog.objects.create(makerspace=world.space, to_email=world.owner.email, subject="Booking", text_body="Update",
        stream="bookings", event="confirmed", feature="bookings", audience="requester", connection_kind="makerspace")
    result = _deliver(log)
    assert result.status == "failed" and result.attempts == 1
    assert legacy.call_args.kwargs["source_intent"] == email_failure_intent(result)
    envelope = NotificationEnvelope.objects.get(makerspace=world.space, recipient=world.staff,
        source_kind="operations.email_failure", source_id=str(log.pk))
    assert envelope.dedup_key == f"p2:{email_failure_intent(log)}:u:{world.staff.pk}"


@pytest.mark.parametrize("legacy_first", [True, False])
def test_failed_email_legacy_mirror_deduplicates_with_envelope(world, legacy_first, monkeypatch):
    from types import SimpleNamespace
    from apps.notifications.legacy_inbox import mirror_legacy_staff
    monkeypatch.setattr("apps.notifications.legacy_inbox._hint", lambda *_: None)
    log = EmailLog.objects.create(makerspace=world.space, to_email="owner@example.test", subject="Update", text_body="Update",
        event="confirmed", status="failed", attempts=1)
    envelope = NotificationEnvelope.objects.get(makerspace=world.space, recipient=world.staff,
        source_kind="operations.email_failure", source_id=str(log.pk))
    def legacy():
        mirror_legacy_staff(world.space, {"event": "email.failed", "title": "Email failed", "body": "Failure", "url_path": ""},
                            source_intent=email_failure_intent(log))
    def personal():
        send_builtin(SimpleNamespace(channel="in_app", envelope=envelope), {"subject": "Email failed", "text": "Failure"})
    (legacy if legacy_first else personal)()
    (personal if legacy_first else legacy)()
    assert NotificationInboxRow.objects.filter(makerspace=world.space, user=world.staff).count() == 1


def test_domain_notification_barrels_use_source_backed_adapters():
    from apps.maintenance.notifications import notify_maintenance_lifecycle
    from apps.procurement.notifications import notify_stock
    from apps.machines.notifications_p2_maintenance import notify as maintenance
    from apps.machines.notifications_p2_stock import notify as procurement
    assert notify_maintenance_lifecycle is maintenance and notify_stock is procurement


@pytest.mark.parametrize("feature,events", [
    ("members", {"joined", "verified", "invitation", "vouched"}), ("payments", {"document_issued"}),
    ("api_access", {"subdomain_request_resolved", "email.failed", "scheduled_report"}),
    ("stock", {"scheduled", "completed"}), ("hardware_requests", {"problem_report.filed"}),
])
def test_followup_events_are_available_in_catalog(feature, events):
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    assert events <= set(FEATURE_EVENTS[feature])


def test_presence_is_a_notification_feature_with_its_choices_migration():
    # Presence was added deliberately (integrations/0037_presence_notification_feature).
    from apps.integrations.notification_enums import NotificationFeature
    assert "presence" in NotificationFeature.values

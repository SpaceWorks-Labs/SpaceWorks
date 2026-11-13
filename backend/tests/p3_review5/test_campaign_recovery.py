"""Campaign progress must never commit ahead of its personal outbox intents."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.integrations import broadcasts_worker as worker
from apps.integrations.notification_outbox import enqueue as enqueue_envelope
from apps.integrations.models_contract import NotificationEnvelope
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


def campaign_for(world, kind):
    space = world.space
    space.enabled_modules = sorted(set(space.enabled_modules) | {"events", "bookings", "email", "notifications"})
    space.enabled_features = sorted(set(space.enabled_features) | {"events.broadcasts", "bookings.broadcasts"})
    space.save()
    if kind == "event_broadcast":
        from apps.events.services_broadcasts import compose, change
        from tests.p2_events.helpers import event, registration
        row = event(space)
        for user in (world.owner, world.other):
            registration(row, user)
        campaign = compose(row, world.staff, subject="News", body="Hello {{ name }}", statuses=["registered"])
        source = "events.broadcast"
    else:
        from apps.bookings.services_broadcasts import compose, change
        from apps.bookings.models import Booking
        Booking.objects.create(space=world.resource, member=world.other, name="Other", email=world.other.email,
            phone="1234567890", status="confirmed", starts_at=world.booking.starts_at + timedelta(hours=2),
            ends_at=world.booking.ends_at + timedelta(hours=2))
        campaign = compose(world.resource, world.staff, subject="News", body="Hello {{ name }}",
            window_start=timezone.now(), window_end=timezone.now() + timedelta(days=7))
        source = "bookings.broadcast"
        for user in (world.owner, world.other):
            NotificationPreference.objects.create(makerspace=space, user=user, category="bookings",
                channels=["in_app"], email_fallback=False)
    return campaign, change, source


@pytest.mark.parametrize("kind", ["event_broadcast", "booking_broadcast"])
@pytest.mark.parametrize("lost", ["initial", "continuation"])
def test_recovery_retries_missing_batches_without_losing_personal_recipients(
        world, monkeypatch, django_capture_on_commit_callbacks, kind, lost):
    campaign, change, source = campaign_for(world, kind)
    monkeypatch.setattr(worker, "BATCH_SIZE", 1)
    broker = Mock(side_effect=ConnectionError("broker down"))
    monkeypatch.setattr(worker.broadcast_batch, "delay", broker)
    with django_capture_on_commit_callbacks(execute=True):
        change(campaign, world.staff, "queue")
    assert broker.called
    assert not NotificationEnvelope.objects.filter(source_kind=source).exists()
    if lost == "continuation":
        broker.reset_mock()
        with django_capture_on_commit_callbacks(execute=True):
            worker.broadcast_batch(kind, campaign.pk)
        campaign.refresh_from_db()
        assert campaign.recipient_cursor == world.owner.pk
        assert not campaign.recipients_complete
        assert broker.called  # the next enqueue failed after this batch committed
        assert NotificationEnvelope.objects.filter(source_kind=source).count() == 1
    broker.side_effect = None
    for _ in range(3):
        broker.reset_mock()
        worker.resume_broadcasts()
        assert (kind, campaign.pk) in [call.args for call in broker.call_args_list]
        worker.broadcast_batch(kind, campaign.pk)
        campaign.refresh_from_db()
        if campaign.recipients_complete:
            break
    assert campaign.recipients_complete
    rows = NotificationEnvelope.objects.filter(source_kind=source, source_id=str(campaign.pk))
    assert set(rows.values_list("recipient_id", flat=True)) == {world.owner.pk, world.other.pk}
    worker.broadcast_batch(kind, campaign.pk)
    assert rows.count() == 2
    if kind == "event_broadcast":
        # These accounts have no verified email, but still receive chat/inbox intents.
        assert not campaign.deliveries.exists()
        assert all(list(row.deliveries.values_list("channel", "state")) == [("email", "skipped")] for row in rows)
    else:
        assert not campaign.deliveries.exists()  # selected personal channels own the entire delivery


@pytest.mark.parametrize("kind", ["event_broadcast", "booking_broadcast"])
def test_envelope_insert_failure_rolls_back_batch_and_cursor(world, monkeypatch, kind):
    from apps.integrations import notification_outbox
    campaign, change, source = campaign_for(world, kind)
    change(campaign, world.staff, "queue")
    real = notification_outbox.emit
    attempts = []
    def fail_second(**kwargs):
        result = real(**kwargs)
        attempts.append(result.pk)
        if len(attempts) == 2:
            raise RuntimeError("lost envelope write")
        return result
    monkeypatch.setattr(notification_outbox, "emit", fail_second)
    with pytest.raises(RuntimeError, match="lost envelope write"):
        worker.broadcast_batch(kind, campaign.pk)
    campaign.refresh_from_db()
    assert campaign.status == "queued" and campaign.recipient_cursor == 0 and not campaign.recipients_complete
    assert not NotificationEnvelope.objects.filter(source_kind=source).exists()
    monkeypatch.setattr(notification_outbox, "emit", real)
    worker.broadcast_batch(kind, campaign.pk)
    assert NotificationEnvelope.objects.filter(source_kind=source).count() == 2


def test_event_email_pipeline_still_owns_the_single_email_leg(world):
    from apps.integrations.models import NotificationPreference as TenantPreference
    campaign, change, source = campaign_for(world, "event_broadcast")
    world.owner.email_verified_at = timezone.now()
    world.owner.save()
    TenantPreference.objects.create(makerspace=world.space, feature="events", channel="email", enabled=True)
    change(campaign, world.staff, "queue")
    worker.broadcast_batch("event_broadcast", campaign.pk)
    assert campaign.deliveries.count() == 1
    assert campaign.deliveries.get().recipient_id == world.owner.pk
    assert NotificationEnvelope.objects.filter(source_kind=source).count() == 2
    envelope = NotificationEnvelope.objects.get(source_kind=source, recipient=world.owner)
    assert list(envelope.deliveries.values_list("channel", "state")) == [("email", "skipped")]


def test_member_broadcast_insert_failure_rolls_back_the_whole_send(world, monkeypatch):
    from apps.notifications.broadcasts import send_broadcast
    from apps.notifications.models_broadcasts import MemberBroadcast
    from apps.operations import notifications_p2
    real = notifications_p2.emit
    calls = []
    def fail_second(**kwargs):
        result = real(**kwargs)
        calls.append(result.pk)
        if len(calls) == 2:
            raise RuntimeError("lost member intent")
        return result
    monkeypatch.setattr(notifications_p2, "emit", fail_second)
    with pytest.raises(RuntimeError, match="lost member intent"):
        send_broadcast(world.space, actor=world.staff, title="News", body="Open today")
    assert not MemberBroadcast.objects.filter(makerspace=world.space).exists()
    assert not NotificationEnvelope.objects.filter(source_kind="membership.broadcast").exists()
    monkeypatch.setattr(notifications_p2, "emit", real)
    row, count = send_broadcast(world.space, actor=world.staff, title="News", body="Open today")
    assert NotificationEnvelope.objects.filter(source_kind="membership.broadcast", source_id=str(row.pk)).count() == count


def test_member_broadcast_broker_loss_leaves_every_intent_recoverable(
        world, monkeypatch, django_capture_on_commit_callbacks):
    from apps.notifications.broadcasts import send_broadcast
    from apps.integrations.notification_tasks import deliver_envelope
    from apps.integrations import notification_outbox
    # Restore the production enqueue patched out by the isolation fixture.
    monkeypatch.setattr(notification_outbox, "enqueue", enqueue_envelope)
    broker = Mock(side_effect=ConnectionError("offline"))
    monkeypatch.setattr(deliver_envelope, "delay", broker)
    with django_capture_on_commit_callbacks(execute=True):
        row, count = send_broadcast(world.space, actor=world.staff, title="News", body="Open today")
    assert broker.call_count == count
    assert NotificationEnvelope.objects.filter(source_kind="membership.broadcast", source_id=str(row.pk)).count() == count

    from apps.integrations.notification_tasks import sweep_notification_outbox
    broker.reset_mock()
    broker.side_effect = None
    sweep_notification_outbox()
    expected = set(NotificationEnvelope.objects.filter(source_kind="membership.broadcast").values_list("pk", flat=True))
    assert expected <= {call.args[0] for call in broker.call_args_list}

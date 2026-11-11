from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.notification_envelopes import new_intent, owner_envelope
from apps.integrations.models_recipients import NotificationRecipient
from apps.integrations.notification_delivery import ensure_deliveries
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_resolution import resolve
from apps.integrations.notification_sources import source_eligible
from apps.integrations.notification_tasks import deliver_envelope
from apps.makerspaces.models import Makerspace
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_preferences import NotificationPreference
from tests.p2_events.helpers import event, registration

pytestmark = pytest.mark.django_db


def queued_notice(lane, kind, mode):
    host = Makerspace.objects.create(name="Event host", slug="event-host")
    row = event(host)
    entry = registration(row, lane.owner)
    entry.registered_via_makerspace = lane.space
    entry.save(update_fields=["registered_via_makerspace"])
    NotificationPreference.objects.create(makerspace=lane.space, user=lane.owner, category="events",
                                          channels=["in_app"], email_fallback=False)
    if kind == "lifecycle":
        envelope = owner_envelope(row, "registration_approved", entry, new_intent())
    else:
        envelope = emit(makerspace=lane.space, recipient=lane.owner, feature="events", stream="events",
            event="reminder", audience="requester", dedup_key=f"review3:reminder:{entry.pk}",
            source_kind="events.reminder", source_id=str(entry.pk), subject=entry,
            context={"event_id": row.pk, "registration_id": entry.pk, "starts_at": row.starts_at.isoformat()},
            rendered={"subject": "Reminder", "text": "Event starts soon"})
    assert envelope is not None and envelope.makerspace_id == lane.space.pk
    assert source_eligible(envelope)
    assert [target.channel for target in resolve(envelope)] == ["in_app"]
    deliveries = list(ensure_deliveries(envelope))
    assert len(deliveries) == 1
    delivery = deliveries[0]
    if mode == "retry":
        delivery.attempt_count = 1
        delivery.last_error = "provider_error"
        delivery.save(update_fields=["attempt_count", "last_error"])
    elif mode == "release":
        envelope.timing_policy = "deferred"
        envelope.available_at = timezone.now() - timedelta(seconds=1)
        envelope.save(update_fields=["timing_policy", "available_at"])
    return host, envelope, delivery


@pytest.mark.parametrize("kind", ["lifecycle", "reminder"])
@pytest.mark.parametrize("mode", ["send", "retry", "release"])
def test_host_archive_blocks_other_tenants_queued_event_content(lane, kind, mode):
    host, envelope, delivery = queued_notice(lane, kind, mode)
    host.archived_at = timezone.now()
    host.save(update_fields=["archived_at"])
    assert not source_eligible(envelope)
    assert resolve(envelope) == []
    deliver_envelope(envelope.pk)
    delivery.refresh_from_db()
    assert delivery.state == "skipped"
    assert not NotificationInboxRow.objects.filter(user=lane.owner).exists()


@pytest.mark.parametrize("kind", ["lifecycle", "reminder"])
@pytest.mark.parametrize("mode", ["send", "retry", "release"])
def test_current_requester_selection_applies_at_send_retry_and_release(lane, kind, mode):
    host, envelope, delivery = queued_notice(lane, kind, mode)
    # Selections in the HOST must not override this registrant's provenance tenant.
    NotificationRecipient.objects.create(makerspace=host, feature="events", event=envelope.event,
        kind="role", role=host.roles.get(slug="event_manager"))
    assert source_eligible(envelope)
    staff = NotificationRecipient.objects.create(makerspace=lane.space, feature="events", event=envelope.event,
        kind="role", role=lane.space.roles.get(slug="event_manager"))
    requester = NotificationRecipient.objects.create(makerspace=lane.space, feature="events",
                                                     event=envelope.event, kind="requester")
    assert source_eligible(envelope)
    requester.delete()  # The manager keeps staff selected but removes the requester.
    assert staff.pk and not source_eligible(envelope)
    assert resolve(envelope) == []
    deliver_envelope(envelope.pk)
    delivery.refresh_from_db()
    assert delivery.state == "skipped"
    assert not NotificationInboxRow.objects.filter(user=lane.owner).exists()


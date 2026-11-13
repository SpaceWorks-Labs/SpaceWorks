from types import SimpleNamespace as Bag

import pytest
from django.utils import timezone

from apps.integrations.models_recipients import NotificationRecipient
from apps.integrations.notification_resolution import eligible
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.notifications.models_preferences import NotificationPreference

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("feature,kind", [("bookings", "bookings.lifecycle"), ("members", "membership.lifecycle"),
    ("members", "membership.application"), ("members", "membership.term"), ("members", "membership.vouch"),
    ("payments", "payments.ledger"), ("payments", "payments.document"), ("certifications", "machines.certification")])
@pytest.mark.parametrize("phase", ["send", "retry", "release"])
def test_shared_requester_selection_is_rechecked(world, monkeypatch, feature, kind, phase):
    # Domain checks are isolated here: this verifies selection at the shared transport seam.
    monkeypatch.setattr("apps.integrations.notification_resolution.source_eligible", lambda _: True)
    monkeypatch.setattr("apps.integrations.recipients.feature_available", lambda *_, **__: True)
    world.space.enabled_modules = sorted(set(world.space.enabled_modules) | {"notifications", "bookings", "membership", "procurement", "machines"})
    world.space.save(update_fields=["enabled_modules"])
    monkeypatch.setattr("apps.integrations.notification_resolution.target_eligible", lambda *_: True)
    NotificationPreference.objects.create(makerspace=world.space, user=world.owner,
        category=feature, channels=["in_app"], email_fallback=False)
    envelope = world.envelope(feature=feature, source_kind=kind)
    assert eligible(envelope)
    delivery = list(ensure_deliveries(envelope))[0]
    if phase == "retry":
        delivery.attempt_count = 1
        delivery.save()
    elif phase == "release":
        envelope.timing_policy, envelope.available_at = "deferred", timezone.now()
        envelope.save()
    NotificationRecipient.objects.create(makerspace=world.space, feature=feature,
        event=envelope.event, kind="user", user=world.staff)
    assert not eligible(envelope)
    send(delivery.pk)
    delivery.refresh_from_db()
    assert delivery.state == "skipped"


def test_inventory_threshold_uses_inventory_gate_independent_of_procurement(world):
    from apps.integrations.recipients_selection import category_available, feature_available
    world.space.enabled_features = [key for key in world.space.enabled_features if key not in {"inventory.tobuy", "machines.tobuy"}]
    world.space.save(update_fields=["enabled_features"])
    assert feature_available(world.space, "stock", source_kind="inventory.threshold")
    assert feature_available(world.space, "hardware_requests", source_kind="inventory.watch")
    assert category_available(world.space, "stock")
    assert not feature_available(world.space, "stock", source_kind="machines.procurement")


@pytest.mark.parametrize("kind", ["membership.lifecycle", "membership.application", "payments.ledger",
                                    "devices.state_edge", "makerspaces.subdomain", "apiclients.request", "operations.stocktake"])
def test_shared_rooms_recheck_sources_and_current_staff(world, monkeypatch, kind):
    from apps.hardware_requests.notifications_p2_rooms import eligible_room
    monkeypatch.setattr("apps.integrations.recipients.feature_available", lambda *_, **__: True)
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_rooms.is_notification_enabled", lambda *_: True)
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_rooms.resolve_destinations", lambda *_: [None])
    monkeypatch.setattr("apps.integrations.staff_notifications.staff_user_ids_for_feature", lambda *_: [world.staff.pk])
    allowed = [True]
    inspected = []
    def source(envelope):
        inspected.append(envelope)
        return allowed[0]
    monkeypatch.setattr("apps.hardware_requests.notifications_p2_rooms.source_eligible", source)
    log = Bag(makerspace=world.space, destination_id=None, feature="members", channel="telegram", event="joined",
        payload={"p2_intent": "key", "source_kind": kind, "source_id": "17", "revision": "revision",
                 "context": {"verification_id": 99}, "scope": {}})
    assert eligible_room(log)
    assert inspected[0].context == {"verification_id": 99} and inspected[0].recipient_id == world.staff.pk
    allowed[0] = False
    assert not eligible_room(log)
    allowed[0] = True
    world.space.archived_at = timezone.now()
    world.space.save(update_fields=["archived_at"])
    assert not eligible_room(log)


def test_legacy_event_rooms_recheck_the_host_after_archival(world):
    from apps.events.notification_envelopes import _context, lifecycle_revision
    from apps.hardware_requests.notifications_p2_rooms import eligible_room
    from tests.p2_events.helpers import event
    from apps.makerspaces.models import Makerspace
    host = Makerspace.objects.create(name="Host", slug="review4-host")
    row = event(host)
    source = {"source_kind": "events.lifecycle", "source_id": f"e{row.pk}",
              "revision": lifecycle_revision(row, None), "context": _context(row, None, "published")}
    # Host-space path proves the gate before and after archival. Organizer paths
    # add their live organization link through the same source predicate.
    log = Bag(makerspace=host, feature="events", event="published", payload={"lifecycle_source": source})
    assert eligible_room(log)
    host.archived_at = timezone.now()
    host.save(update_fields=["archived_at"])
    assert not eligible_room(log)


def test_legacy_booking_rooms_reject_an_old_revision(world):
    from apps.hardware_requests.notifications_p2_rooms import eligible_room
    log = Bag(makerspace=world.space, feature="bookings", event="confirmed", payload={"lifecycle_source": {
        "source_kind": "bookings.lifecycle", "source_id": str(world.booking.pk),
        "revision": str(world.booking.calendar_sequence), "context": {}}})
    assert eligible_room(log)
    world.booking.calendar_sequence += 1
    world.booking.save()
    assert not eligible_room(log)

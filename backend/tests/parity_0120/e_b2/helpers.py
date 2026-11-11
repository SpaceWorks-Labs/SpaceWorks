"""Shared builders for the E-B2 tests (badge desk data, role detection, receipts)."""
from django.utils import timezone

from apps.card_designs import badge_format, designs, resolution
from apps.events import id_cards
from apps.events.models import Event, EventIdCard, EventRegistration
from tests.l3_local.helpers import card_space, manager, member

FEATURES = ("events.id_cards", "events.badge_designer", "events.badge_desk_print", "events.role_badges",
            "events.crew")


def live_event(slug, features=FEATURES):
    space = card_space(slug, features=features)
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Build Night", status="published",
                                 starts_at=now - timezone.timedelta(hours=1), ends_at=now + timezone.timedelta(hours=3))
    return space, event, manager(space)


def register(space, event, name="attendee", **fields):
    user, _membership = member(space, name)
    row = EventRegistration.objects.create(event=event, member=user, name=user.username, email=user.email,
                                           status=EventRegistration.Status.REGISTERED, **fields)
    return user, row


def publish_badge(space, event, sm, role=None, **settings):
    """Save + publish a badge_v1 design for the event (attendee) or for one role variant."""
    if role is None:
        design, _ = resolution.get_or_create(space, "event_card", actor=sm, event=event)
    else:
        from apps.card_designs import resolution_roles
        base, _ = resolution.get_or_create(space, "event_card", actor=sm, event=event)
        design, _ = resolution_roles.get_or_create_variant(event, role, document=base.document, actor=sm)
    document = {"version": 2, "source": {"format": "badge_v1", "settings": badge_format.normalize(
        {"colorMode": "colour", **settings})}}
    designs.save(sm, design, document, expected_revision=design.revision)
    design.refresh_from_db()
    designs.publish(sm, design)
    design.refresh_from_db()
    return design


def issue_cards(event):
    id_cards.reconcile_event(event.pk)
    return {card.registration_id: card for card in EventIdCard.objects.filter(event=event)}

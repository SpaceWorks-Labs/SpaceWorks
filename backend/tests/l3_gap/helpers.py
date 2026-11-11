"""Shared fixtures for the ID-card gap lane (r2-gap-cards) local tests."""
from io import BytesIO

from django.utils import timezone

from tests.l3_local.helpers import card_space, manager, member

PROGRAMMES = ("membership.id_programmes",)


def owned_space(slug, features=PROGRAMMES):
    from apps.organizations.models import Organization, OrganizationMakerspace
    space = card_space(slug, features=features)
    org = Organization.objects.create(name=f"Org {slug}", slug=f"org-{slug}")
    OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="owner")
    return space, org


def programme(slug, **values):
    from apps.id_programmes import services
    space, org = owned_space(slug)
    sm = manager(space)
    row = services.create(sm, org, space, {"name": "Student ID", **values})
    services.update(sm, row, {"status": "active", "registration_open": True})
    row.refresh_from_db()
    return space, org, sm, row


def live_event(slug, features=("events.id_cards",)):
    from apps.events.models import Event
    space = card_space(slug, features=features)
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Build Night", starts_at=now - timezone.timedelta(hours=1),
                                 ends_at=now + timezone.timedelta(hours=3), status="published")
    return space, event


def registration(space, event, name="attendee"):
    from apps.events.models import EventRegistration
    user, _m = member(space, name)
    return user, EventRegistration.objects.create(event=event, member=user, name=user.username, email=user.email,
                                                  status=EventRegistration.Status.REGISTERED)


def event_card(space, event, name="attendee"):
    from apps.card_designs import designs, resolution
    from apps.events import id_cards
    from apps.events.models import EventIdCard
    user, row = registration(space, event, name)
    designs.publish(manager(space, "publisher"), resolution.get_or_create(space, "event_card", event=event)[0])
    id_cards.reconcile_event(event.pk)
    return user, EventIdCard.objects.get(registration=row)


def png_bytes(size=(60, 80), colour=(20, 120, 100)):
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def stage(object_key, data=None, content_type="image/png"):
    """Put bytes where the browser's presigned upload would have put them."""
    from apps.card_designs.storage import put_bytes
    from apps.evidence import storage as evidence_storage
    put_bytes(evidence_storage.staging_key(object_key), data or png_bytes(), content_type)

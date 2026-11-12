"""The machines side of "this is for an event" (decision 342): a thin, tombstone-safe seam.

The link is event-owned (`apps.events.machine_use_services`); machines never imports an event model. With the
events module off (or the app tombstoned) there is nothing to link: a named event is refused for a person's own
submission and silently ignored for an adapter, which must never fail a session.
"""
import logging

from django.db import transaction
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _space(subject):
    """The makerspace of a session or request (`makerspace`) or of a booking (via its bookable space)."""
    return getattr(subject, "makerspace", None) or subject.space.makerspace


def _services(space):
    from apps.makerspaces.platform import module_enabled
    if not module_enabled(space, "events"):
        return None
    try:
        from apps.events import machine_use_services
    except ImportError:
        return None
    return machine_use_services


def attach(subject, event_id, *, actor):
    """Requester path (service request, member or staff session start): optional, strict when given."""
    if event_id in (None, ""):
        return None
    services = _services(_space(subject))
    if services is None:
        raise ValidationError({"event_id": gettext("Events are not turned on in this makerspace."),
                               "code": "events_off"})
    return services.attach(subject, event_id, actor=actor)


def attach_quiet(subject, event_id):
    """Adapter path: link only an eligible event; every failure is swallowed so the session still starts."""
    if event_id in (None, ""):
        return None
    try:
        services = _services(_space(subject))
        if services is None:
            return None
        with transaction.atomic():
            return services.attach_quiet(subject, event_id)
    except Exception:  # noqa: BLE001 - an adapter session never fails over an optional label
        logger.warning("machine_event_link_ignored", exc_info=True, extra={"subject_id": subject.pk})
        return None


def manage(actor, subject, event_id):
    """Area manager path: set, change or clear. A no-op when no event is given and none is linked."""
    if event_id is None:
        return None
    services = _services(_space(subject))
    if services is None:
        raise ValidationError({"event_id": gettext("Events are not turned on in this makerspace."),
                               "code": "events_off"})
    return services.manage(actor, subject, event_id)


def event_summary(subject):
    """`{id, title}` of the event a session or request is logged for, or None. Safe with no link or no events app."""
    try:
        link = subject.event_link
    except Exception:  # noqa: BLE001 - RelatedObjectDoesNotExist, or the events app is tombstoned
        return None
    return {"id": link.event_id, "title": link.event.title}


def with_event(queryset):
    """Join the event link (and its event) into a list query, so `event_summary` costs no query per row.

    A no-op when the events app is not installed (the reverse accessor does not exist)."""
    if hasattr(queryset.model, "event_link"):
        return queryset.select_related("event_link__event")
    return queryset


def staff_attach(actor, subject, event_id, *, house=False):
    """Staff booking create: a staff member with machine authority picks any open event of the space (as the
    area manager does); anyone else is held to the event rules of the member booked for. A house booking has no
    member, so only machine authority can tag it."""
    if event_id in (None, ""):
        return None
    services = _services(_space(subject))
    if services is None:
        raise ValidationError({"event_id": gettext("Events are not turned on in this makerspace."), "code": "events_off"})
    if services.may_manage(actor, subject):
        return services.manage(actor, subject, event_id)
    if house:
        raise ValidationError({"event_id": gettext("Choose one of your events."), "code": "event_not_eligible"})
    return services.attach(subject, event_id, actor=actor)

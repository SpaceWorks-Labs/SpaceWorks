"""Signed, minimal webhooks for link changes between events, bookings and loans (interconnection 18).

Same shape as `shop.webhooks`: outbound only, to the space's webhook destinations alone, ids and
the event time only -- never a title, a person, a room name or an amount -- so a destination
fetches any detail through the API under its own scope.

* `events.event_booking_linked` -- an event now holds a venue booking.
* `events.event_loan_linked` / `events.event_loan_unlinked` -- a loan was linked to, or unlinked
  from, an event (moving a loan to another event is an unlink then a link).
* `bookings.booking_loan_linked` / `bookings.booking_loan_unlinked` -- the same for a loan and a booking.

Fail safe: a missing destination, a switched-off webhook cell, a module that is off or a failed
insert never blocks the link workflow; the savepoint keeps the domain transaction intact.
"""

from django.utils.translation import gettext
import logging

from django.db import transaction
from django.utils import timezone
from apps.integrations.fanout_jobs import deferred_fanout

logger = logging.getLogger(__name__)

# event key -> (feature, modules that must all be on, allowed id keys)
LINK_EVENTS = {
    "event_booking_linked": ("events", ("events", "bookings"), ("event_id", "booking_id")),
    "event_loan_linked": ("events", ("events", "request_workflow"), ("event_id", "request_id")),
    "event_loan_unlinked": ("events", ("events", "request_workflow"), ("event_id", "request_id")),
    "booking_loan_linked": ("bookings", ("bookings", "request_workflow"), ("booking_id", "request_id")),
    "booking_loan_unlinked": ("bookings", ("bookings", "request_workflow"), ("booking_id", "request_id")),
}


def link_changes(prefix, old_id, new_id, delete):
    """The (event name, activity id) webhooks for one loan-context write.

    `old_id` is the activity the loan was actively linked to (None if none); `new_id` the target.
    A delete unlinks the old one; a write to a different activity unlinks the old and links the new;
    a write that keeps the same activity (e.g. only the participant changed) is not a link change.
    """
    if delete:
        return [(f"{prefix}_unlinked", old_id)] if old_id else []
    if old_id == new_id:
        return []
    return ([(f"{prefix}_unlinked", old_id)] if old_id else []) + [(f"{prefix}_linked", new_id)]


@deferred_fanout()
def link_webhook(space, event, **ids):
    """Queue `<feature>.<event>` to the space's webhook destinations; False when nothing was queued."""
    from apps.integrations.dispatch_channels import dispatch_channel
    from apps.integrations.notification_catalog import is_notification_enabled
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable

    if event not in LINK_EVENTS:
        raise ValueError("Unknown link webhook event")
    feature, modules, keys = LINK_EVENTS[event]
    try:
        if not (is_servable(space) and all(module_enabled(space, key) for key in modules)
                and is_notification_enabled(space, feature, "webhook")):
            return False
        payload = {key: ids[key] for key in keys if key in ids}
        payload["occurred_at"] = timezone.now().isoformat()
        with transaction.atomic():  # a failed INSERT rolls back its savepoint, not the link
            dispatch_channel(makerspace=space, channel="webhook", feature=feature, event=event,
                             text_body=gettext("Link changed: %(event)s.") % {"event": event.replace("_", " ")}, payload=payload)
        return True
    except Exception as exc:
        logger.warning("link_webhook_failed", extra={"makerspace_id": space.pk, "event": event,
                                                     "failure_type": type(exc).__name__})
        return False

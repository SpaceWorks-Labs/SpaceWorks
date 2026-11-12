"""Offer reservation math; hard seats always use events.capacity."""
from django.utils.translation import gettext
from collections import Counter
from apps.events.capacity import confirmed_occupancy, registration_spots_left, spots_left
from apps.events.models import EventRegistration
from .admission_errors import fail
from .admission_models import HackathonApplication


def occupancy(event, config):
    offered = HackathonApplication.objects.filter(event=event, state="offered").count()
    confirmed = confirmed_occupancy(event)
    ceiling = config.offer_capacity if config.offer_capacity is not None else (event.capacity or None)
    return {"offered": offered, "confirmed": confirmed, "offer_capacity": ceiling,
            "offer_spots_left": None if ceiling is None else max(ceiling - offered - confirmed, 0),
            "hard_spots_left": spots_left(event)}


def require_offer_room(event, config, count):
    left = occupancy(event, config)["offer_spots_left"]
    if left is not None and count > left:
        fail("capacity_full", gettext("There are not enough offer places for this whole group."))


def require_hard_room(event, applications):
    # This is a fresh unannotated locked event, not a cached UI count.
    event_left = spots_left(event)
    if event_left is not None and event_left < len(applications):
        fail("capacity_full", gettext("All confirmed places are taken. You can choose the waitlist."))
    registrations = list(EventRegistration.objects.filter(pk__in=[a.registration_id for a in applications]))
    counts = Counter(r.ticket_type_id for r in registrations)
    for ticket_id, count in counts.items():
        registration = next(r for r in registrations if r.ticket_type_id == ticket_id)
        left = registration_spots_left(event, registration.ticket_type)
        if left is not None and left < count:
            fail("capacity_full", gettext("This ticket has no room for the whole group. You can choose the waitlist."))


def preview(event, config, groups):
    available = occupancy(event, config)["offer_spots_left"]
    offered, skipped = [], []
    for subject_id, size in groups:
        if available is not None and size > available:
            skipped.append({"subject_id": subject_id, "people": size, "reason": "group_does_not_fit"})
            continue
        offered.append(subject_id)
        if available is not None:
            available -= size
    return {"selected": offered, "skipped": skipped, "offer_spots_left": available}

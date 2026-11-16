"""Decision 223 (k), lane L3b: the events half of the attendee-to-member join funnel.

Core (`makerspaces/join_funnel.py`) never imports events; it calls these two functions lazily and only
while the `events` module is on. Both read ATTENDED registrations of events hosted at the space.
"""
from .models import EventRegistration


def registration_prefill(user, makerspace, registration_id):
    """What a "Join" call to action pre-fills for the person who attended, or None (not theirs / not here)."""
    row = (EventRegistration.objects.select_related("event")
           .filter(pk=registration_id, member=user, event__makerspace=makerspace)
           .exclude(status__in=(EventRegistration.Status.CANCELLED, EventRegistration.Status.REJECTED)).first())
    if row is None:
        return None
    return {"name": row.name, "email": row.email, "phone": row.phone, "source": "event",
            "source_ref": row.pk, "source_label": row.event.title}


def first_attendances(makerspace, start=None, end=None):
    """`{user_id: first attended event end}` for attendees whose first attendance at this space fell in range."""
    rows = (EventRegistration.objects.filter(
        event__makerspace=makerspace, status=EventRegistration.Status.ATTENDED, member__isnull=False)
        .values_list("member_id", "event__ends_at").order_by("event__ends_at"))
    first = {}
    for user_id, ended in rows:
        first.setdefault(user_id, ended)
    return {user: ended for user, ended in first.items()
            if (start is None or ended >= start) and (end is None or ended < end)}

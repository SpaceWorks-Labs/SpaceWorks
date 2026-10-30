"""Organisation cross-event insights for the platform view (G8), with k >= 10 suppression.

Each organisation row aggregates the events it organises across every servable space:
event count, registrations and attendance. Any count below K is returned as None and
the row is marked `suppressed`, so a small organisation's numbers can never be narrowed
down to individual people. Rates are only computed from unsuppressed counts.
"""

from django.db.models import Count, Q

K = 10
LIMIT = 20


def _suppress(value):
    return value if value >= K else None


def organization_insights(spaces):
    from apps.events.organizer_models import EventOrganizer
    rows = (EventOrganizer.objects.filter(event__makerspace__in=spaces, organization__is_active=True)
            .values("organization_id", "organization__name")
            .annotate(events=Count("event", distinct=True),
                      registrations=Count("event__registrations", distinct=True,
                                          filter=Q(event__registrations__status__in=("registered", "attended"))),
                      attended=Count("event__registrations", distinct=True,
                                     filter=Q(event__registrations__status="attended")))
            .order_by("-events", "organization_id")[:LIMIT])
    result = []
    for row in rows:
        registrations, attended = _suppress(row["registrations"]), _suppress(row["attended"])
        result.append({
            "organization_id": row["organization_id"], "name": row["organization__name"],
            "events": row["events"], "registrations": registrations, "attended": attended,
            "attendance_percent": (round(attended * 100 / registrations, 1)
                                   if registrations and attended is not None else None),
            "suppressed": registrations is None or attended is None,
        })
    return result

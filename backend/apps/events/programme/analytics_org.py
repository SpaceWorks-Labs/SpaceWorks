"""Organisation cross-event insights for the platform view (G8), with k >= 10 suppression.

`hosted_insights` (parity E-B7) adds the staff view: top events over the last 180 days by people who
attended, and the share of attendees who came to more than one of those events. An event with fewer than K
attendees is left out of the ranking and a returning share is only given for K or more distinct attendees, so
a small group can never be narrowed down to individuals. Names, emails and member ids are never returned.

Each organisation row aggregates the events it organises across every servable space:
event count, registrations and attendance. Any count below K is returned as None and
the row is marked `suppressed`, so a small organisation's numbers can never be narrowed
down to individual people. Rates are only computed from unsuppressed counts.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

K = 10
LIMIT = 20
WINDOW_DAYS = 180
TOP = 10


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


def hosted_insights(events, *, now=None):
    """Top events and returning attendees over `events` (a queryset already scoped by the caller)."""
    now = now or timezone.now()
    window = events.filter(starts_at__gte=now - timedelta(days=WINDOW_DAYS), starts_at__lte=now)
    attended = Q(registrations__status="attended", registrations__is_crew=False)
    ranked = (window.annotate(attended_count=Count("registrations", filter=attended, distinct=True))
              .filter(attended_count__gte=K).order_by("-attended_count", "-starts_at", "pk")[:TOP])
    top = [{"event_id": row.pk, "title": row.title, "starts_at": row.starts_at,
            "attended": row.attended_count} for row in ranked]
    return {"window_days": WINDOW_DAYS, "k": K, "top_events": top, "returning": returning_share(window)}


def returning_share(window):
    """Share of distinct signed-in attendees who attended two or more events in the window, or suppressed."""
    from apps.events.models import EventRegistration
    per_member = (EventRegistration.objects.filter(event__in=window.values("pk"), status="attended",
                                                   is_crew=False, member__isnull=False)
                  .values("member_id").annotate(events=Count("event_id", distinct=True)))
    total = per_member.count()
    if total < K:
        return {"suppressed": True, "attendees": None, "returning_percent": None}
    returning = per_member.filter(events__gte=2).count()
    return {"suppressed": False, "attendees": total, "returning_percent": round(returning * 100 / total, 1)}

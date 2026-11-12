"""Live public event badges using personal ownership and durable provenance."""

from django.db.models import Case, CharField, F, Q, Value, When
from django.utils import timezone

from .platform import module_enabled
from .profile_activity_sources import attended_registrations
from .profile_history_speaking import speaking_contributions


PRIORITY = {"ATTENDED": 1, "HOSTED": 2, "SPOKE": 3}


def _scope_badges(scope, badges):
    """One space's contribution (decision 304c: the global profile merges every listed space)."""
    if not module_enabled(scope.membership.makerspace, "events"):
        return
    from apps.events.event_authority import active_grants
    from apps.events.models import Event
    from apps.events.member_history import registrations_for_space
    from apps.events.organizer_authority import organizer_event_q

    def put(pk, badge):
        if PRIORITY[badge] > PRIORITY.get(badges.get(pk), 0):
            badges[pk] = badge

    speaking = speaking_contributions(scope) if scope.show_speaking else []
    if scope.show_events:
        for pk in attended_registrations(scope).values_list("event_id", flat=True):
            put(pk, "ATTENDED")
        # Being staff in one space or a collaborator TODAY is not participation in
        # every event. Remote host history needs the member-history provenance.
        provenance = registrations_for_space(scope.membership.makerspace, scope.membership.user)
        grants = active_grants(scope.membership.user).filter(
            Q(permissions__contains=["edit_details"]) | Q(permissions__contains=["publish_schedule"]),
        ).exclude(role_label="speaker")
        hosts = Event.objects.filter(
            Q(makerspace_id=scope.membership.makerspace_id)
            | Q(pk__in=provenance.values("event_id")),
        ).filter(
            organizer_event_q(scope.membership.user)
            | Q(created_by_id=scope.membership.user_id)
            | Q(pk__in=grants.filter(event__isnull=False).values("event_id"))
            | Q(series_id__in=grants.filter(series__isnull=False).values("series_id")),
            starts_at__lte=timezone.now(), is_public=True, status__in=["published", "completed"],
        )
        for pk in hosts.values_list("pk", flat=True).distinct():
            put(pk, "HOSTED")
    # The frozen response has one badge, so choose the most specific participation.
    # An event appears once even when this person attended, hosted AND spoke there.
    for row in speaking:
        put(row.event.pk, "SPOKE")


def event_history(account):
    from apps.events.models import Event

    from .profile_activity_public import scopes_for

    badges = {}
    for scope in scopes_for(account):
        _scope_badges(scope, badges)
    # Keep this lazy so DRF applies count/limit/offset in PostgreSQL, rather than
    # loading the member's entire event payload before taking one page.
    return Event.objects.filter(
        pk__in=badges, is_public=True, listing="listed", page_state="live", status__in=["published", "completed"],
    ).order_by("-starts_at", "-pk").annotate(badge=Case(
        When(pk__in=[pk for pk, badge in badges.items() if badge == "SPOKE"], then=Value("SPOKE")),
        When(pk__in=[pk for pk, badge in badges.items() if badge == "HOSTED"], then=Value("HOSTED")),
        default=Value("ATTENDED"), output_field=CharField(),
    )).values("title", "starts_at", "ends_at", "badge", host=F("makerspace__name"))

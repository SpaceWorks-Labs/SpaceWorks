"""Live public event badges using personal ownership and durable provenance."""

from django.db.models import Case, CharField, F, Q, Value, When
from django.utils import timezone

from .platform import module_enabled
from .profile_activity_sources import attended_registrations
from .profile_history_speaking import speaking_contributions


def event_history(profile):
    if not module_enabled(profile.membership.makerspace, "events"):
        return []
    from apps.events.event_authority import active_grants
    from apps.events.models import Event
    from apps.events.member_history import registrations_for_space
    from apps.events.organizer_authority import organizer_event_q

    badges = {}
    speaking = speaking_contributions(profile) if profile.show_speaking else []
    if profile.show_events:
        for pk in attended_registrations(profile).values_list("event_id", flat=True):
            badges[pk] = "ATTENDED"
        # Being staff in one space or a collaborator TODAY is not participation in
        # every event. Remote host history needs the member-history provenance.
        provenance = registrations_for_space(profile.membership.makerspace, profile.membership.user)
        grants = active_grants(profile.membership.user).filter(
            Q(permissions__contains=["edit_details"]) | Q(permissions__contains=["publish_schedule"]),
        ).exclude(role_label="speaker")
        hosts = Event.objects.filter(
            Q(makerspace_id=profile.membership.makerspace_id)
            | Q(pk__in=provenance.values("event_id")),
        ).filter(
            organizer_event_q(profile.membership.user)
            | Q(created_by_id=profile.membership.user_id)
            | Q(pk__in=grants.filter(event__isnull=False).values("event_id"))
            | Q(series_id__in=grants.filter(series__isnull=False).values("series_id")),
            starts_at__lte=timezone.now(), is_public=True, status__in=["published", "completed"],
        )
        for pk in hosts.values_list("pk", flat=True).distinct():
            badges[pk] = "HOSTED"
    # The frozen response has one badge, so choose the most specific participation.
    # An event appears once even when this person attended, hosted AND spoke there.
    for row in speaking:
        badges[row.event.pk] = "SPOKE"
    # Keep this lazy so DRF applies count/limit/offset in PostgreSQL, rather than
    # loading the member's entire event payload before taking one page.
    return Event.objects.filter(
        pk__in=badges, is_public=True, status__in=["published", "completed"],
    ).order_by("-starts_at", "-pk").annotate(badge=Case(
        When(pk__in=[pk for pk, badge in badges.items() if badge == "SPOKE"], then=Value("SPOKE")),
        When(pk__in=[pk for pk, badge in badges.items() if badge == "HOSTED"], then=Value("HOSTED")),
        default=Value("ATTENDED"), output_field=CharField(),
    )).values("title", "starts_at", "ends_at", "badge", host=F("makerspace__name"))

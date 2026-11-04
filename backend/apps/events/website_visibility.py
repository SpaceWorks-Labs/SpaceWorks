"""One event gate for every public website projection, including image bytes."""

from django.db.models import Count, Q, Value
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import servable_q
from apps.makerspaces.website_visibility import released_page
from .models import Event
from .models_website import EventPage
from .capacity import CONFIRMED_STATUSES


def public_q(prefix=""):
    """The ACCESS gate shared by every token-addressed public surface: visible and live.

    Listing is deliberately absent: an unlisted event is reachable by anyone holding
    its link or code. An offline page is gone from every public surface without
    changing the event's lifecycle status.
    """
    return Q(**{f"{prefix}is_public": True, f"{prefix}page_state": Event.PageState.LIVE})


def listed_q(prefix=""):
    """The LISTING gate: access plus "who can find it = listed"."""
    return public_q(prefix) & Q(**{f"{prefix}listing": Event.Listing.LISTED})


def public_events(makerspace):
    # The calling API retains its module error.
    return Event.objects.filter(public_q(), makerspace=makerspace,
                               status=Event.Status.PUBLISHED, ends_at__gte=timezone.now())


def listed_events(makerspace):
    """Every surface that LISTS events (event list, Pages collections, directories)."""
    return public_events(makerspace).filter(listing=Event.Listing.LISTED)


def resolve(makerspace_slug, token):
    from apps.makerspaces.editions import require_public_surface
    require_public_surface("events")
    if makerspace_slug is None:
        event = get_object_or_404(Event.objects.select_related("makerspace"), public_token=token)
        makerspace_slug = event.makerspace.slug
    space = get_public_makerspace(makerspace_slug)
    if not module_enabled(space, "events"):
        raise Http404
    return get_object_or_404(public_events(space).select_related(
        "makerspace", "makerspace__payment_settings", "series", "category"), public_token=token)


def effective_page(event):
    page = EventPage.objects.filter(event=event).first()
    return page or (EventPage.objects.filter(series_id=event.series_id).first() if event.series_id else None)


def visible_page(event):
    from apps.makerspaces.editions import require_public_surface
    require_public_surface("events")
    # The public-site switch hides the event website (JSON, images, cover share)
    # as one decision; the core event detail stays governed by its own gate.
    if not event.makerspace.public_site_enabled or not public_events(event.makerspace).filter(pk=event.pk).exists():
        raise Http404
    page = released_page(event, "events", effective_page(event))
    if page.published_revision_id is None:
        raise Http404
    return page


def discover_events(spaces, filters=None):
    from apps.makerspaces.editions import public_surface_available
    from apps.makerspaces.module_registry import module_available
    if not public_surface_available("events") or not module_available("events"):
        return Event.objects.none()
    filters = filters or {}
    rows = Event.objects.filter(
        servable_q("makerspace"), listed_q(), makerspace__in=spaces,
        makerspace__enabled_modules__contains=["events"],
        status=Event.Status.PUBLISHED, ends_at__gte=timezone.now(),
    ).select_related(
        "makerspace", "series", "website_page__published_revision",
        "series__website_page__published_revision",
    ).prefetch_related("organizers").annotate(
        # This query already enforces canonical tenant servability. Card
        # projection can inspect loaded feature configuration without a fresh
        # opaque-restore lookup for every row. Never persist this read proof.
        website_host_servable=Value(True),
        confirmed_count=Count("registrations", filter=Q(registrations__status__in=CONFIRMED_STATUSES,
                                                         registrations__is_crew=False)),
    ).order_by("starts_at", "id")

    from apps.inventory.search import apply_q
    if filters.get("q"):
        rows = apply_q(rows, filters["q"], label_field="title")
    if filters.get("date_from") or filters.get("date_to"):
        from apps.makerspaces.local_time import local_date_expression
        rows = rows.alias(website_local_day=local_date_expression("starts_at", "makerspace__timezone"))
    if filters.get("date_from"):
        rows = rows.filter(website_local_day__gte=filters["date_from"])
    if filters.get("date_to"):
        rows = rows.filter(website_local_day__lte=filters["date_to"])
    return rows

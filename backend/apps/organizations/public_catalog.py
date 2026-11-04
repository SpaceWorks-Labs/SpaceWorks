"""P5 uses organizer attribution, including events at unlinked venues."""
from django.db.models import Exists, OuterRef, Count, Q
from django.utils import timezone
from apps.makerspaces.website_directory import directory_spaces
from apps.separability.registry import runtime_active


def linked_spaces_for(organization):
    if not organization.is_active or not organization.public_profile_enabled:
        return directory_spaces().none()
    from apps.makerspaces.module_registry import module_available
    from apps.makerspaces.editions import public_surface_available
    destination = Q(public_page__published_revision__isnull=False, public_handle__isnull=False)
    for family in ("events", "bookings", "machines", "membership"):
        if module_available(family) and public_surface_available(family):
            destination |= Q(enabled_modules__contains=[family])
    if module_available("public_inventory") and public_surface_available("public_inventory"):
        destination |= Q(public_inventory_enabled=True, enabled_modules__contains=["public_inventory"],
                         enabled_features__contains=["loans.enabled"])
    return directory_spaces().filter(destination, organization_links__organization=organization).select_related(
        "public_page", "public_handle").distinct().order_by("name", "id")


def public_events_for(organization, *, period="upcoming", now=None):
    if not runtime_active("events"):
        return None
    from apps.events.models import Event
    from apps.events.organizer_models import EventOrganizer
    from apps.events.website_visibility import listed_q
    from apps.makerspaces.editions import public_surface_available
    from apps.makerspaces.module_registry import module_available
    if (not organization.is_active or not organization.public_profile_enabled
            or not module_available("events") or not public_surface_available("events")):
        return Event.objects.none()
    now = now or timezone.now()
    organized = EventOrganizer.objects.filter(event_id=OuterRef("pk"), organization=organization)
    rows = Event.objects.filter(
        Exists(organized), listed_q(), makerspace__in=directory_spaces(),
        makerspace__enabled_modules__contains=["events"],
    ).select_related("makerspace__payment_settings").prefetch_related("organizers__organization")
    if period == "past":
        return rows.filter(status__in=("published", "completed"), ends_at__lt=now).order_by("-ends_at", "-id")
    return rows.filter(status="published", ends_at__gte=now).annotate(confirmed_count=Count("registrations", filter=Q(
        registrations__status__in=("registered", "attended"), registrations__is_crew=False))).order_by("starts_at", "id")


def space_card(space):
    from apps.inventory.public_image_storage import public_url
    from apps.makerspaces.public_page_access import canonical_url
    claim = getattr(space, "public_handle", None)
    page = getattr(space, "public_page", None)
    handle = claim.handle if claim and page and page.published_revision_id else None
    return {"name": space.name, "slug": space.slug, "logo_url": public_url(space.logo_key) or None,
            "canonical_url": canonical_url("makerspace", space, handle)}


def archive_card(event):
    from apps.makerspaces.public_page_markdown import excerpt
    from apps.makerspaces.public_page_access import canonical_url
    return {"kind": "archive", "title": event.title, "description": excerpt(event.description),
            "starts_at": event.starts_at, "ends_at": event.ends_at, "timezone": event.makerspace.timezone,
            "event_url": None, "host": {"name": event.makerspace.name,
                "canonical_url": canonical_url("makerspace", event.makerspace)}}

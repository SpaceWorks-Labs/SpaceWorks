"""One booking public predicate; resources have no event lifecycle or expiry."""

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.makerspaces.editions import require_public_surface, public_surface_available
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.module_registry import module_available
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.website_visibility import released_page
from .models import BookableSpace
from .models_website import BookingResourcePage


def public_spaces(makerspace):
    # Extracted unchanged from views_public. Directory consent is an extra gate.
    return BookableSpace.objects.filter(makerspace=makerspace, is_public=True, is_active=True)


def resolve(makerspace_slug, token):
    require_public_surface("bookings")
    if makerspace_slug is None:
        subject = get_object_or_404(BookableSpace.objects.select_related("makerspace"), public_token=token)
        makerspace_slug = subject.makerspace.slug
    tenant = get_public_makerspace(makerspace_slug)
    if not module_enabled(tenant, "bookings"):
        raise Http404
    return get_object_or_404(public_spaces(tenant).select_related("makerspace"), public_token=token)


def page_for(space):
    return BookingResourcePage.objects.filter(space=space).first()


def visible_page(space):
    # Re-resolve live tenant/resource state even for callers holding a stale instance.
    current = resolve(space.makerspace.slug, space.public_token)
    return released_page(current, "bookings", page_for(current))


def discover_spaces(tenants, filters=None):
    if not module_available("bookings") or not public_surface_available("bookings"):
        return BookableSpace.objects.none()
    filters = filters or {}
    rows = BookableSpace.objects.filter(
        makerspace__in=tenants, makerspace__enabled_modules__contains=["bookings"],
        is_public=True, is_active=True,
    ).select_related("makerspace", "website_page").order_by("name", "id")
    if filters.get("q"):
        # BookableSpace has no trigger-maintained search_vector. Keep bounded
        # catalogue text search on its public descriptive fields.
        query = filters["q"]
        rows = rows.filter(Q(name__icontains=query) | Q(description__icontains=query)
                           | Q(location__icontains=query))
    if filters.get("kind"):
        rows = rows.filter(kind=filters["kind"])
    if filters.get("location"):
        rows = rows.filter(location__icontains=filters["location"])
    return rows

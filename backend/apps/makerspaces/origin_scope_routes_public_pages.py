"""Explicit page owners; global organization routes never select a tenant."""

from django.apps import apps

from apps.accounts.claim_routes_public_pages import MAKERSPACE_PAGE_EDITORS, ORGANIZATION_PAGE_EDITORS

GLOBAL_ROUTES = ORGANIZATION_PAGE_EDITORS | frozenset({
    "public-organization-page", "public-organization-page-asset",
    "public-organization-makerspaces",
})
HANDLE_ROUTES = frozenset({"public-page-handle", "public-page-share", "public-page-cover-share"})
EVENT_ROUTES = frozenset({"public-event-code", "public-event-code-share", "public-event-cover-share"})
EVENT_CODE_ROUTES = frozenset({"public-event-short-code", "public-event-short-code-share",
                               "public-event-short-code-cover-share"})
SLUG_ROUTES = frozenset({"public-makerspace-page", "public-makerspace-page-asset"})


def page_route_targets(name, kwargs, request):
    if name in GLOBAL_ROUTES:
        return name, set(), False, True
    if name in MAKERSPACE_PAGE_EDITORS:
        target = apps.get_model("makerspaces.Makerspace").objects.filter(pk=kwargs.get("pk")).values_list("pk", flat=True).first()
    elif name in HANDLE_ROUTES:
        from .public_page_access import resolve_handle
        try:
            claim, result = resolve_handle(kwargs.get("handle"), request)
        except Exception:
            return name, set(), True, True
        if result["kind"] == "organization":
            return name, set(), False, True
        target = claim.makerspace_id or claim.profile.membership.makerspace_id
    elif name in EVENT_ROUTES:
        # Venue ownership, never an organizer's linked makerspaces.
        if not apps.is_installed("apps.events"):
            return name, set(), True, True
        target = apps.get_model("events.Event").objects.filter(public_token=kwargs.get("public_token")).values_list("makerspace_id", flat=True).first()
    elif name in EVENT_CODE_ROUTES:
        if not apps.is_installed("apps.events"):
            return name, set(), True, True
        target = apps.get_model("events.EventShortLink").objects.filter(
            code=kwargs.get("code"), retired_at__isnull=True).values_list("makerspace_id", flat=True).first()
    elif name in SLUG_ROUTES:
        from .lookup import get_public_makerspace
        from django.http import Http404
        try:
            target = get_public_makerspace(kwargs.get("makerspace_slug")).pk
        except Http404:
            target = None
    else:
        return None
    return name, {target} if target is not None else set(), target is None, True


def organization_editor_origin_allowed(request):
    """Global governance pages use a platform Host and the platform staff origin."""
    from django.conf import settings
    from .public_profile_access import _request_tenant_ids
    from .origin_scope import _origin_candidate
    try:
        scopes = _request_tenant_ids(request)
    except Exception:
        return False
    origin = _origin_candidate(request)
    return not scopes and (not origin or origin in settings.PLATFORM_STAFF_ORIGINS)

"""Native `X-Makerspace-Id` on routes that name their space by slug.

Members reach `/public/{makerspace_slug}/...` and `/public/m/{makerspace_slug}/shop/...` with a
native device grant. A route not otherwise registered in the origin-scope tables still owns its
space through the slug, so a native selection is checked against it: a match is allowed, a
mismatch or an unresolvable slug is refused (403), exactly like `PUBLIC_SLUG_ROUTES`.

This is native-selection validation only. It deliberately does not feed
`authoritative_route_resolution`, so it adds no tenant-RLS binding, source-gate target or
staff-origin target to these public routes.
"""

from django.http import Http404


def native_slug_targets(request):
    """``(targets, invalid)`` for a slug-owned route, or ``None`` when the route has no slug."""
    kwargs = getattr(getattr(request, "resolver_match", None), "kwargs", None) or {}
    if "makerspace_slug" not in kwargs:
        return None
    from .lookup import get_public_makerspace

    try:
        return {get_public_makerspace(kwargs["makerspace_slug"]).pk}, False
    except Http404:
        return set(), True

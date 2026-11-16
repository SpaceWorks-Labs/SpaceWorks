"""Frontend URLs and origins of a makerspace: member area, payment return, staff settings links.

Split out of `platform.py` (300-line ceiling); `platform.py` re-exports every name, so
`from apps.makerspaces.platform import member_area_url` keeps resolving.
"""
from urllib.parse import urlencode, urlparse

from django.conf import settings

from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import is_servable, public_availability_queryset, servable_queryset


def origin_to_hostname(origin):
    if not origin:
        return ""
    parsed = urlparse(origin if "://" in origin else f"//{origin}")
    return (parsed.hostname or "").lower()


def makerspace_staff_origins(makerspace):
    origins = set(settings.PLATFORM_STAFF_ORIGINS)
    if (
        makerspace.frontend_domain
        and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED
    ):
        origins.add(f"https://{makerspace.frontend_domain}")
    return origins


def makerspace_public_origins(makerspace):
    return makerspace_staff_origins(makerspace) | set(makerspace.cors_allowed_origins or [])


def member_area_url(makerspace):
    """Return the canonical member-area URL for a makerspace frontend."""
    if (
        makerspace.frontend_domain
        and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED
    ):
        return f"https://{makerspace.frontend_domain}/member"
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{base}/m/{makerspace.slug}/member" if base and makerspace.slug else ""


def member_payment_return_url(makerspace):
    """Where a payer lands after checkout, including when the makerspace is archived.

    `member_area_url` sends them to the tenant's own member area, which for an ARCHIVED space
    is a dead end: its custom domain has lost bootstrap and origin trust, and `/m/<slug>/member`
    cannot resolve the tenant either. Returning someone there immediately after they paid
    strands them on a 404 holding a charge they have just settled. The recovery route is
    authentication-only and always lives on the central app, so it is reachable regardless of
    what happened to the tenant's domain.
    """
    if not is_servable(makerspace):
        base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
        return f"{base}/member/archived" if base else ""
    return member_area_url(makerspace)


# Where a fix link lands: the exact routed Settings section (`/admin/settings/<section>`,
# ids from frontend/src/features/staff/settingsSections.ts), never the bare Settings root.
SETTINGS_FIX_PATHS = {
    "payments": "settings/money",
    "health": "settings/health",
    "branding": "settings/branding",
    "integrations": "settings/integrations",
}


def staff_payment_settings_url(makerspace=None, *, outcome):
    """Return a trusted staff settings URL without accepting browser input."""
    verified_domain = (
        makerspace is not None
        and makerspace.frontend_domain
        and makerspace.frontend_domain_status == Makerspace.DomainStatus.VERIFIED
    )
    if verified_domain:
        base = f"https://{makerspace.frontend_domain}"
    else:
        base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    section = SETTINGS_FIX_PATHS["payments"]
    path = (
        f"/admin/{section}"
        if verified_domain
        else f"/m/{makerspace.slug}/admin/{section}"
        if makerspace is not None and makerspace.slug
        else f"/admin/{section}"
    )
    return f"{base}{path}?{urlencode({'stripe_connect': outcome})}"


def _frontend_rows(*, tenant=None, slug=None, origin=None, host=None):
    if tenant:
        return Makerspace.objects.filter(public_code__iexact=tenant)
    if slug:
        return Makerspace.objects.filter(slug=slug)
    hostname = origin_to_hostname(origin) or origin_to_hostname(host)
    if hostname:
        return Makerspace.objects.filter(frontend_domain__iexact=hostname)
    return None


def resolve_frontend(*, tenant=None, slug=None, origin=None, host=None):
    rows = _frontend_rows(tenant=tenant, slug=slug, origin=origin, host=host)
    return None if rows is None else servable_queryset(rows).first()


def paused_frontend(**lookup):
    """#185(1): whether the lookup names a space that is paused (not archived, not unknown).

    Lets a space served on its own domain or tenant token show "This space is paused"
    instead of falling back to the central site; it reveals no more than the public
    availability endpoint does for a slug."""
    rows = _frontend_rows(**lookup)
    return rows is not None and public_availability_queryset(rows).filter(
        lifecycle_state=Makerspace.LifecycleState.SUSPENDED,
    ).exists()

"""Live typed visibility and Host + browser-origin authorization. Uniform 404s."""

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import NotFound
from .models import Makerspace
from .models_profiles import PublicHandle, PublicHandleRedirect
from .public_page_adapters import adapter
from .public_profile_access import _request_tenant_ids, resolve_public_profile
from .servability import is_servable
from .hosting import canonical_host


def _verified_domain(space):
    return bool(space and space.frontend_domain and space.frontend_domain_status == Makerspace.DomainStatus.VERIFIED)


def canonical_origin(space=None):
    if _verified_domain(space):
        return f"https://{space.frontend_domain}"
    return settings.PUBLIC_APP_BASE_URL.rstrip("/")


def _public_home_organization(space):
    from apps.organizations.models import Organization
    return Organization.objects.filter(
        makerspace_links__makerspace=space, makerspace_links__relationship="owner",
        is_active=True, public_profile_enabled=True, review_status="approved",
    ).order_by("pk").first()


def canonical_url(kind, owner, handle=None):
    origin = canonical_origin(owner if kind == "makerspace" else None)
    if handle:
        return f"{origin}/{handle}"
    if kind == "makerspace" and _verified_domain(owner):
        # A verified tenant domain boots the single-space SPA, which has no /m/<slug> route.
        return f"{origin}/"
    if kind == "makerspace" and getattr(owner, "kind", "makerspace") == "organization":
        # Decision 295: an organization workspace has no /m/ page; its public face is /o/<slug>.
        organization = _public_home_organization(owner)
        if organization is not None:
            return f"{canonical_origin(None)}/o/{organization.slug}"
    return f"{origin}/{'m' if kind == 'makerspace' else 'o'}/{owner.slug}"


def require_scope(kind, owner, request):
    # Both kinds fail closed on unknown Hosts and browser Origins/Referers. A tenant
    # Origin may read a global organization page; a tenant Host may not serve one.
    scopes = _request_tenant_ids(request)
    if kind == "makerspace":
        if any(pk != owner.pk for pk in scopes):
            raise NotFound()
        return
    # An infra IP host has no canonical name; None must never become an isnull match.
    host = canonical_host(request.get_host())
    if host and Makerspace.objects.filter(frontend_domain__iexact=host).exists():
        raise NotFound()


def public_page(kind, owner, request=None):
    if kind == "makerspace":
        if not owner.public_site_enabled or not is_servable(owner):
            raise NotFound()
    elif (not owner.is_active or not owner.public_profile_enabled
            or owner.review_status != "approved"):  # pending/declined/suspended orgs are inert
        raise NotFound()
    if request:
        require_scope(kind, owner, request)
    page = adapter(kind).page.objects.select_related("published_revision").filter(**{kind: owner}).first()
    if page is None or page.published_revision_id is None:
        raise NotFound()
    return page


def resolve_handle(handle, request=None, viewer=None):
    claim = PublicHandle.objects.filter(handle__iexact=handle).first()
    redirected = False
    if claim is None:
        retired = PublicHandleRedirect.objects.filter(handle__iexact=handle, expires_at__gt=timezone.now()).first()
        if retired:
            kind = "user" if retired.user_id else "makerspace" if retired.makerspace_id else "organization"
            claim = PublicHandle.objects.filter(**{f"{kind}_id": getattr(retired, f"{kind}_id")}).first()
            redirected = claim is not None
    if claim is None:
        raise NotFound()
    if claim.user_id:
        resolve_public_profile(claim.handle, request, viewer)  # one 404 unless readable by this viewer
        from .public_profile_share import profile_url
        return claim, {"kind": "member", "handle": claim.handle, "canonical_url": profile_url(claim.handle),
                       "redirected": redirected, "content_url": f"/api/v1/public/profiles/{claim.handle}/"}
    kind = "makerspace" if claim.makerspace_id else "organization"
    owner = getattr(claim, kind)
    public_page(kind, owner, request)
    path = f"/api/v1/public/{owner.slug}/page/" if kind == "makerspace" else f"/api/v1/public/organizations/{owner.slug}/page/"
    return claim, {"kind": kind, "handle": claim.handle, "canonical_url": canonical_url(kind, owner, claim.handle),
                   "redirected": redirected, "content_url": path}

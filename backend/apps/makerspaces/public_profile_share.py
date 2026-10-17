"""Share/sitemap adapters; routing belongs to the integration lane.

Resolve live consent BEFORE serving any cached card. Sitemap consumers must call
the iterator on each read, rather than caching an unfiltered publication list.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from .models_profiles import PublicHandle
from .public_profile_access import resolve_public_profile, profile_is_public, _request_tenant_ids
from .public_profile_views import PublicProfileBase, ERRORS
from .profile_services import display_name_for
from .website_serving import PublicCard, share_response
from .public_profile_cache import remember_share_card
from apps.inventory.public_image_storage import public_url


def profile_url(claim):
    space = claim.profile.membership.makerspace
    if space.frontend_domain and space.frontend_domain_status == space.DomainStatus.VERIFIED:
        origin = f"https://{space.frontend_domain}"
    else:
        origin = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{origin}/{claim.handle}"


class PublicProfileShareView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[], responses={
        (200, "text/html"): OpenApiResponse(str, description="Live-gated OG/Twitter share metadata."),
        302: OpenApiResponse(description="Redirect to the current public handle."), **ERRORS,
    })
    def get(self, request, handle):
        self.cache_headers()
        claim, redirected = resolve_public_profile(handle, request)
        if redirected:
            return Response(status=302, headers={"Location": f"/share/profiles/{claim.handle}/"})
        profile = claim.profile
        card = PublicCard(
            title=display_name_for(profile.membership), description=profile.bio,
            url=profile_url(claim), image_url=public_url(profile.avatar_key) or None,
            date="", location="", availability="", audience_label="Public maker profile",
            revision=f"{profile.updated_at.isoformat()}:{claim.changed_at.isoformat()}",
        )
        response = share_response(card)
        remember_share_card(profile.pk, card)
        return response


def sitemap_profile_urls(request, *, spaces=None):
    if spaces is None:
        from .website_directory import sitemap_spaces
        spaces = sitemap_spaces(request)
    try:
        scopes = _request_tenant_ids(request)
    except NotFound:
        # An unscoped host or origin publishes no profiles; it must not 404 the shared sitemap.
        return
    claims = PublicHandle.objects.select_related("profile__membership__user", "profile__membership__makerspace")
    claims = claims.filter(profile__membership__makerspace__in=spaces)
    if scopes:
        if len(set(scopes)) != 1:
            return
        claims = claims.filter(profile__membership__makerspace_id=scopes[0])
    for claim in claims.iterator(chunk_size=200):
        if claim.user_id == claim.profile.membership.user_id and profile_is_public(claim.profile):
            yield profile_url(claim)

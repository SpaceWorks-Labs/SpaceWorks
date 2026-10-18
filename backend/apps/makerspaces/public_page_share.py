"""Crawler metadata reruns typed live visibility, even when static caching fails."""

from urllib.parse import urljoin
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from .public_profile_views import PublicProfileBase
from .public_page_access import resolve_handle, public_page
from .public_page_projection import projection
from .website_serving import PublicCard, share_response


class PublicPageShareView(PublicProfileBase):
    @extend_schema(tags=["Public pages"], auth=[], responses={
        (200, "text/html"): OpenApiResponse(str, description="Live public-page OG/Twitter metadata."),
        302: OpenApiResponse(description="Current public canonical URL."), 404: OpenApiResponse(description="Unavailable page.")})
    def get(self, request, handle):
        self.cache_headers()
        claim, resolution = resolve_handle(handle, request)
        if resolution["redirected"]:
            return Response(status=302, headers={"Location": resolution["canonical_url"]})
        if resolution["kind"] == "member":
            from .public_profile_share import PublicProfileShareView
            return PublicProfileShareView.get(self, request, claim.handle)
        kind = resolution["kind"]
        owner = getattr(claim, kind)
        payload = projection(kind, owner, public_page(kind, owner, request), request=request)
        cover = payload["cover"]
        response = share_response(PublicCard(title=payload["title"], description=payload["description"],
            url=payload["canonical_url"], image_url=urljoin(payload["canonical_url"], cover["url"]) if cover else None,
            image_alt=cover["alt"] if cover else "", date="", location="", availability="", audience_label="Public page",
            revision=payload["publication_token"]))
        response["Cache-Control"] = "no-store"
        return response


def sitemap_page_urls(request, *, spaces):
    from .models_profiles import PublicHandle
    from .public_page_access import canonical_url
    from rest_framework.exceptions import NotFound
    claims = PublicHandle.objects.filter(makerspace__in=spaces).select_related("makerspace")
    for claim in claims:
        try:
            public_page("makerspace", claim.makerspace, request)
        except NotFound:
            continue
        yield canonical_url("makerspace", claim.makerspace, claim.handle)
    for claim in PublicHandle.objects.filter(organization__is_active=True, organization__public_profile_enabled=True).select_related("organization"):
        try:
            public_page("organization", claim.organization, request)
        except NotFound:
            continue
        yield canonical_url("organization", claim.organization, claim.handle)

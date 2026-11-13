"""Crawler metadata reruns typed live visibility, even when static caching fails."""

from urllib.parse import urljoin
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from .public_profile_views import PublicProfileBase
from .public_page_access import canonical_origin, resolve_handle, public_page
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
        page = public_page(kind, owner, request)
        payload = projection(kind, owner, page, request=request)
        cover, image_url = payload["cover"], None
        if cover and page.published_revision.document["cover_mode"] == "asset":
            # Page assets sit behind API-client auth; crawlers send no client headers.
            image_url = f"{cover_origin(kind, owner)}/share/pages/{claim.handle}/cover/"
        elif cover:
            image_url = urljoin(payload["canonical_url"], cover["url"])
        response = share_response(PublicCard(title=payload["title"], description=payload["description"],
            url=payload["canonical_url"], image_url=image_url,
            image_alt=cover["alt"] if cover else "", date="", location="", availability="", audience_label="Public page",
            revision=payload["publication_token"]))
        response["Cache-Control"] = "no-store"
        return response


def cover_origin(kind, owner):
    return canonical_origin(owner if kind == "makerspace" else None)


class PublicPageCoverShareView(PublicProfileBase):
    @extend_schema(tags=["Public pages"], auth=[], responses={
        200: OpenApiResponse(bytes, description="Current published cover WebP; private, no-store."),
        404: OpenApiResponse(description="Unavailable page, redirected or member handle, or no published asset cover."),
        429: OpenApiResponse(description="Rate limit exceeded."),
        503: OpenApiResponse(description="Image storage is unavailable.")})
    def get(self, request, handle):
        from .public_page_asset_views import image
        from .public_page_assets import public_asset_ids
        self.cache_headers()
        claim, resolution = resolve_handle(handle, request)
        if resolution["redirected"] or resolution["kind"] == "member":
            raise NotFound()
        kind = resolution["kind"]
        owner = getattr(claim, kind)
        page = public_page(kind, owner, request)
        revision = page.published_revision
        cover_id = revision.document["cover_mode"] == "asset" and revision.document["cover_asset_id"]
        if not cover_id or cover_id not in public_asset_ids(revision):
            raise NotFound()
        return image(get_object_or_404(page.assets, pk=cover_id), kind, owner.pk)


def sitemap_page_urls(request, *, spaces):
    """Bulk form of public_page(): one query per owner kind, scope resolved once."""
    from .models_profiles import PublicHandle
    from .public_page_access import canonical_url, require_scope
    from .public_profile_access import _request_tenant_ids
    from .servability import servable_q
    try:
        scopes = _request_tenant_ids(request)
    except NotFound:
        return
    claims = PublicHandle.objects.filter(
        servable_q("makerspace"), makerspace__in=spaces, makerspace__public_site_enabled=True,
        makerspace__public_page__published_revision__isnull=False,
    ).select_related("makerspace").order_by("pk")
    for claim in claims:
        if not any(pk != claim.makerspace_id for pk in scopes):
            yield canonical_url("makerspace", claim.makerspace, claim.handle)
    try:
        require_scope("organization", None, request)  # A tenant Host lists no organizations.
    except NotFound:
        return
    for claim in PublicHandle.objects.filter(
            organization__is_active=True, organization__public_profile_enabled=True,
            organization__review_status="approved",
            organization__public_page__published_revision__isnull=False,
    ).select_related("organization").order_by("pk"):
        yield canonical_url("organization", claim.organization, claim.handle)

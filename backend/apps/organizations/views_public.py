from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.organizations.models import Organization
from apps.organizations.serializers_public import PublicOrganizationSerializer, OrganizationSpaceListSerializer


PUBLIC_ERRORS = {
    404: OpenApiResponse(description="Organization not found."),
    429: OpenApiResponse(description="Rate limit exceeded."),
}
# Paginated collections also refuse a malformed or out-of-range `page` (and `period`).
COLLECTION_ERRORS = {
    400: OpenApiResponse(description="Invalid page or period query parameter."),
    **PUBLIC_ERRORS,
}


def _public_organization(slug):
    owner = get_object_or_404(
        Organization.objects.filter(is_active=True, public_profile_enabled=True),
        slug=slug,
    )
    from rest_framework.exceptions import NotFound
    page = getattr(owner, "public_page", None)
    if page and page.published_revision_id is None:
        raise NotFound()
    return owner


class PublicOrganizationDetailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(
        tags=["Public organizations"],
        summary="Retrieve a public organization profile",
        auth=[],
        request=None,
        responses={200: PublicOrganizationSerializer, **PUBLIC_ERRORS},
    )
    def get(self, request, slug):
        # Legacy profiles are global compatibility reads. Builder pages and assets
        # enforce Host/Origin scope separately; live consent still applies here.
        response = Response(PublicOrganizationSerializer(_public_organization(slug)).data)
        response["Cache-Control"] = "no-store"
        return response




class PublicOrganizationMakerspacesView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public organizations"], auth=[], parameters=[OpenApiParameter("page", int)],
                   responses={200: OrganizationSpaceListSerializer, **COLLECTION_ERRORS})
    def get(self, request, slug):
        from apps.makerspaces.public_profile_access import _request_tenant_ids
        from apps.makerspaces.public_page_pagination import PagePagination
        from .public_catalog import linked_spaces_for, space_card
        _request_tenant_ids(request)
        owner = _public_organization(slug)
        from apps.makerspaces.public_page_access import require_scope
        require_scope("organization", owner, request)
        paginator = PagePagination()
        page = paginator.paginate_queryset(linked_spaces_for(owner), request, view=self)
        response = paginator.get_paginated_response([space_card(row) for row in page])
        response["Cache-Control"] = "no-store"
        return response


def __getattr__(name):
    if name == "PublicOrganizationEventListView":
        from apps.separability.registry import runtime_active
        if runtime_active("events"):
            from .views_public_events import PublicOrganizationEventListView
            return PublicOrganizationEventListView
    raise AttributeError(name)

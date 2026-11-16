from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.organizations.public_directory import directory_card, directory_enabled, directory_organizations


class PublicOrganizationCardSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    description = serializers.CharField()
    logo_url = serializers.CharField(allow_null=True)
    canonical_url = serializers.CharField()


class PublicOrganizationDirectorySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = PublicOrganizationCardSerializer(many=True)


class PublicOrganizationDirectoryView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(
        tags=["Public organizations"], summary="List opt-in public organizations", auth=[],
        parameters=[OpenApiParameter("page", int), OpenApiParameter("search", str, description="Name contains.")],
        responses={200: PublicOrganizationDirectorySerializer,
                   400: OpenApiResponse(description="Invalid page."),
                   404: OpenApiResponse(description="The directory is switched off, or this host lists no organizations."),
                   429: OpenApiResponse(description="Rate limit exceeded.")},
    )
    def get(self, request):
        from apps.makerspaces.public_page_access import require_scope
        from apps.makerspaces.public_page_pagination import PagePagination
        if not directory_enabled():
            raise NotFound()
        require_scope("organization", None, request)  # a tenant Host lists no organizations
        paginator = PagePagination()
        rows = paginator.paginate_queryset(
            directory_organizations(request.query_params.get("search", "")), request, view=self)
        response = paginator.get_paginated_response([directory_card(row) for row in rows])
        response["Cache-Control"] = "no-store"
        return response

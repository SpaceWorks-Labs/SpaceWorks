"""Searchable organization and partner-makerspace directories for event staff."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.inventory import public_image_storage

from . import directories


class DirectorySearchThrottle(SimpleRateThrottle):
    scope = "event_directory_search"
    rate = "120/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class _DirectoryPagination(PageNumberPagination):
    page_size = 24


class DirectoryOrganizationSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)
    logo_url = serializers.SerializerMethodField()

    def get_logo_url(self, obj) -> str | None:
        return public_image_storage.public_url(obj.logo_key) or None


class DirectoryMakerspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.SlugField(read_only=True)


def _page_serializer(name, row):
    return type(name, (serializers.Serializer,), {
        "count": serializers.IntegerField(), "next": serializers.CharField(allow_null=True),
        "previous": serializers.CharField(allow_null=True), "results": row(many=True),
    })


OrganizationDirectoryPageSerializer = _page_serializer("OrganizationDirectoryPage", DirectoryOrganizationSerializer)
MakerspaceDirectoryPageSerializer = _page_serializer("MakerspaceDirectoryPage", DirectoryMakerspaceSerializer)
SEARCH = OpenApiParameter("search", OpenApiTypes.STR, OpenApiParameter.QUERY,
                          description="Case-insensitive substring of the name or slug.")
PAGE = OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY)
ERRORS = {
    401: OpenApiResponse(ErrorSerializer, description="Authentication is required."),
    403: OpenApiResponse(ErrorSerializer, description="Event management access is required."),
    429: OpenApiResponse(ErrorSerializer, description="Directory search rate limit exceeded."),
}


class _DirectoryView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [DirectorySearchThrottle]
    row_serializer = None

    def rows(self, request):
        raise NotImplementedError

    def get(self, request):
        directories.require_event_staff(request.user)
        paginator = _DirectoryPagination()
        rows = directories.search(self.rows(request), request.query_params.get("search"))
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(self.row_serializer(page, many=True).data)


class OrganizationDirectoryView(_DirectoryView):
    row_serializer = DirectoryOrganizationSerializer

    def rows(self, request):
        return directories.discoverable_organizations(request.user)

    @extend_schema(
        tags=["Admin events"], summary="Search the organization directory",
        description=("Active organizations that opted into discovery, plus the actor's own "
                     "organizations. Used to pick an event's audience organizations."),
        parameters=[SEARCH, PAGE], request=None,
        responses={200: OrganizationDirectoryPageSerializer, **ERRORS},
    )
    def get(self, request):
        return super().get(request)


class PartnerMakerspaceDirectoryView(_DirectoryView):
    row_serializer = DirectoryMakerspaceSerializer

    def rows(self, request):
        rows = directories.partner_makerspaces(request.user)
        exclude = request.query_params.get("exclude", "")
        return rows.exclude(pk=int(exclude)) if exclude.isdigit() else rows

    @extend_schema(
        tags=["Admin events"], summary="Search makerspaces that can partner on an event",
        description=("Servable makerspaces running events that are listed in the central "
                     "directory, plus spaces the actor manages events in."),
        parameters=[SEARCH, PAGE, OpenApiParameter(
            "exclude", OpenApiTypes.INT, OpenApiParameter.QUERY,
            description="Makerspace id to leave out, normally the host.")],
        request=None, responses={200: MakerspaceDirectoryPageSerializer, **ERRORS},
    )
    def get(self, request):
        return super().get(request)

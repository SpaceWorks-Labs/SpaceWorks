"""Staff routes for sending and cancelling hosting invitations.

Makerspace routes carry ``makerspace_id`` in the path, so origin scoping and the
authenticated source gate resolve their tenant. Organization routes have no tenant and
are central-origin only, like every other organization governance route.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hosting_requests import authority, workflow
from apps.hosting_requests.availability import require_public_available
from apps.hosting_requests.models import HostingRequest
from apps.hosting_requests.serializers import (
    HostingInvitationCreateSerializer,
    HostingInvitationCreatedSerializer,
    HostingInvitationPageSerializer,
    HostingInvitationSerializer,
)
from apps.openapi_errors import errors

TAGS = ["Hosting requests"]
READ_ERRORS = errors(401, 403, 404)
WRITE_ERRORS = errors(400, 401, 403, 404, 409, 429)


class HostingInvitationCreateThrottle(UserRateThrottle):
    scope = "hosting_invitation_create"

    def allow_request(self, request, view):
        # Only creation spends the budget; listing and cancelling are free.
        return request.method != "POST" or super().allow_request(request, view)


def _page(queryset, request, view):
    paginator = PageNumberPagination()
    rows = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response(HostingInvitationSerializer(rows, many=True).data)


def _created(request, **scope):
    serializer = HostingInvitationCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    row, url, delivery = workflow.create_invitation(request.user, **scope, **serializer.validated_data)
    payload = {**HostingInvitationSerializer(row).data, "invite_url": url, "delivery_status": delivery}
    response = Response(payload, status=status.HTTP_201_CREATED)
    response["Cache-Control"] = "no-store"
    return response


class MakerspaceHostingInvitationsView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [HostingInvitationCreateThrottle]

    @extend_schema(tags=TAGS, summary="List this makerspace's hosting invitations",
                   responses={200: HostingInvitationPageSerializer, **READ_ERRORS})
    def get(self, request, makerspace_id):
        require_public_available()
        authority.resolve_makerspace_inviter(request.user, makerspace_id)
        return _page(HostingRequest.objects.filter(
            inviter_kind=HostingRequest.InviterKind.MAKERSPACE, inviter_makerspace_id=makerspace_id,
        ), request, self)

    @extend_schema(tags=TAGS, summary="Invite someone to host a makerspace on this platform",
                   description="The invitation link is returned once and never again.",
                   request=HostingInvitationCreateSerializer,
                   responses={201: HostingInvitationCreatedSerializer, **WRITE_ERRORS})
    def post(self, request, makerspace_id):
        require_public_available()
        return _created(request, makerspace_id=makerspace_id)


class MakerspaceHostingInvitationCancelView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Cancel a makerspace's hosting invitation", request=None,
                   responses={200: HostingInvitationSerializer, **WRITE_ERRORS})
    def post(self, request, makerspace_id, pk):
        require_public_available()
        row = workflow.cancel_invitation(request.user, pk=pk, makerspace_id=makerspace_id)
        return Response(HostingInvitationSerializer(row).data)


class OrganizationHostingInvitationsView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [HostingInvitationCreateThrottle]

    @extend_schema(tags=TAGS, summary="List this organization's hosting invitations",
                   responses={200: HostingInvitationPageSerializer, **READ_ERRORS})
    def get(self, request, pk):
        require_public_available()
        authority.require_organization_reader(request.user, pk)
        return _page(HostingRequest.objects.filter(
            inviter_kind=HostingRequest.InviterKind.ORGANIZATION, inviter_organization_id=pk,
        ), request, self)

    @extend_schema(tags=TAGS, summary="Invite someone to host a makerspace with this organization",
                   description="The invitation link is returned once and never again.",
                   request=HostingInvitationCreateSerializer,
                   responses={201: HostingInvitationCreatedSerializer, **WRITE_ERRORS})
    def post(self, request, pk):
        require_public_available()
        return _created(request, organization_id=pk)


class OrganizationHostingInvitationCancelView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Cancel an organization's hosting invitation", request=None,
                   responses={200: HostingInvitationSerializer, **WRITE_ERRORS})
    def post(self, request, pk, invitation_id):
        require_public_available()
        row = workflow.cancel_invitation(request.user, pk=invitation_id, organization_id=pk)
        return Response(HostingInvitationSerializer(row).data)

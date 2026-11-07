"""Platform request queues in the web superadmin console (#190, parity with /control/).

Space Managers' archive requests, API key requests and web address requests across every
space, decided through the same services as the /control/ actions (``archive_requests``,
``key_request_decisions``, ``subdomain_decisions``), which lock, audit and notify. Lists
name the space and the request, never the requester's contact details.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.apiclients import key_request_decisions
from apps.apiclients.models import ApiKeyRequest
from apps.makerspaces import archive_requests, subdomain_decisions
from apps.makerspaces.models import MakerspaceArchiveRequest, SubdomainRequest
from apps.openapi_errors import errors

TAGS = ["Platform requests"]
STATUS = OpenApiParameter("status", str, required=False, description="Only requests in this state.")


class ArchiveRequestRowSerializer(serializers.ModelSerializer):
    makerspace_name = serializers.CharField(source="makerspace.name", read_only=True)

    class Meta:
        model = MakerspaceArchiveRequest
        fields = ("id", "makerspace", "makerspace_name", "status", "reason", "resolution_note", "requested_at",
                  "resolved_at")
        read_only_fields = fields


class ApiKeyRequestRowSerializer(serializers.ModelSerializer):
    makerspace_name = serializers.CharField(source="makerspace.name", read_only=True)

    class Meta:
        model = ApiKeyRequest
        fields = ("id", "makerspace", "makerspace_name", "label", "reason", "allowed_origins", "status",
                  "created_at", "resolved_at")
        read_only_fields = fields


class SubdomainRequestRowSerializer(serializers.ModelSerializer):
    makerspace_name = serializers.CharField(source="makerspace.name", read_only=True)

    class Meta:
        model = SubdomainRequest
        fields = ("id", "makerspace", "makerspace_name", "requested_label", "status", "created_at", "decided_at")
        read_only_fields = fields


class QueueDecisionNoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class IssuedClientSerializer(serializers.Serializer):
    request = ApiKeyRequestRowSerializer()
    client_id = serializers.CharField()
    client_secret = serializers.CharField(help_text="Shown once. Copy it now; it cannot be shown again.")


def _listing(view, request, queryset, serializer):
    status = request.query_params.get("status")
    if status in queryset.model.Status.values:
        queryset = queryset.filter(status=status)
    page = view.paginate_queryset(queryset.select_related("makerspace"))
    return view.get_paginated_response(serializer(page, many=True).data)


def _refused(exc):
    return ValidationError({"detail": getattr(exc, "message", None) or " ".join(exc.messages)})


def _gated(model, pk):
    """The row, after the space's source gate admits a write (as /control/'s admin gate does)."""
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    row = get_object_or_404(model, pk=pk)
    assert_write_allowed(row.makerspace_id)
    return row


class _Decision(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]


class ArchiveRequestListView(GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = ArchiveRequestRowSerializer

    @extend_schema(tags=TAGS, summary="List archive requests from every space", parameters=[STATUS],
                   responses={200: ArchiveRequestRowSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        return _listing(self, request, MakerspaceArchiveRequest.objects.order_by("-requested_at"),
                        ArchiveRequestRowSerializer)


class ArchiveRequestDecideView(_Decision):
    approve = True

    @extend_schema(tags=TAGS, summary="Approve (archives the space now) or decline an archive request",
                   request=QueueDecisionNoteSerializer, responses={200: ArchiveRequestRowSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        body = QueueDecisionNoteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = get_object_or_404(MakerspaceArchiveRequest, pk=pk)
        note = body.validated_data["note"]
        decided = (archive_requests.approve(row, request.user, note) if self.approve
                   else archive_requests.decline(row, request.user, note))
        return Response(ArchiveRequestRowSerializer(decided).data)


class ArchiveRequestDeclineView(ArchiveRequestDecideView):
    approve = False


class ApiKeyRequestListView(GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = ApiKeyRequestRowSerializer

    @extend_schema(tags=TAGS, summary="List API key requests from every space", parameters=[STATUS],
                   responses={200: ApiKeyRequestRowSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        return _listing(self, request, ApiKeyRequest.objects.order_by("-created_at"), ApiKeyRequestRowSerializer)


class ApiKeyRequestApproveView(_Decision):
    @extend_schema(tags=TAGS, summary="Approve an API key request and issue its server client", request=None,
                   responses={200: IssuedClientSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        try:
            row, client, secret = key_request_decisions.approve(request.user, _gated(ApiKeyRequest, pk))
        except DjangoValidationError as exc:
            raise _refused(exc) from None
        response = Response({"request": ApiKeyRequestRowSerializer(row).data, "client_id": client.client_id,
                             "client_secret": secret})
        response["Cache-Control"] = "private, no-store"  # a one-time secret: never cached
        return response


class ApiKeyRequestRejectView(_Decision):
    @extend_schema(tags=TAGS, summary="Reject an API key request", request=None,
                   responses={200: ApiKeyRequestRowSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        try:
            row = key_request_decisions.reject(request.user, _gated(ApiKeyRequest, pk))
        except DjangoValidationError as exc:
            raise _refused(exc) from None
        return Response(ApiKeyRequestRowSerializer(row).data)


class SubdomainRequestListView(GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = SubdomainRequestRowSerializer

    @extend_schema(tags=TAGS, summary="List web address requests from every space", parameters=[STATUS],
                   responses={200: SubdomainRequestRowSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        return _listing(self, request, SubdomainRequest.objects.order_by("-created_at"),
                        SubdomainRequestRowSerializer)


class SubdomainRequestApproveView(_Decision):
    @extend_schema(tags=TAGS, summary="Approve a web address request and provision it", request=None,
                   responses={200: SubdomainRequestRowSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        try:
            row = subdomain_decisions.approve(request.user, _gated(SubdomainRequest, pk))
        except DjangoValidationError as exc:
            raise _refused(exc) from None
        return Response(SubdomainRequestRowSerializer(row).data)


class SubdomainRequestRejectView(_Decision):
    @extend_schema(tags=TAGS, summary="Reject a web address request", request=None,
                   responses={200: SubdomainRequestRowSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        try:
            row = subdomain_decisions.reject(request.user, _gated(SubdomainRequest, pk))
        except DjangoValidationError as exc:
            raise _refused(exc) from None
        return Response(SubdomainRequestRowSerializer(row).data)

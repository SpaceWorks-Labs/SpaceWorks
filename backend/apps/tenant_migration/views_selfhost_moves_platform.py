"""Self-host move requests in the web superadmin console (#190, parity with /control/ Self-host moves).

Every request across the platform; approve or decline it, run the export with the target
server's one-shot age key, delete the export file, and download it through a short-lived,
one-use link. The same services as /control/ (``selfhost_move``) make every change and
write every audit row; decisions and the file deletion pass the space's source gate like
the /control/ form does.
"""

import hashlib
from datetime import timedelta

from django.core import signing
from django.core.cache import cache
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.openapi_errors import errors

from . import selfhost_move as moves
from .gate_runtime import assert_write_allowed
from .models_selfhost_move import SelfHostMoveRequest

TAGS = ["Tenant migration"]
SALT = "selfhost-move-download"
LINK_SECONDS = 300


class PlatformMoveSerializer(serializers.ModelSerializer):
    makerspace_name = serializers.CharField(source="makerspace.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    has_file = serializers.SerializerMethodField()

    class Meta:
        model = SelfHostMoveRequest
        fields = ("id", "makerspace", "makerspace_name", "status", "status_label", "note", "requested_at",
                  "decided_at", "decision_note", "recipient_fingerprint", "exported_at", "artifact_sha256",
                  "failure_code", "has_file")
        read_only_fields = fields

    def get_has_file(self, obj) -> bool:
        return bool(obj.artifact_path)


class MoveDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ExportSerializer(serializers.Serializer):
    recipient = serializers.CharField(max_length=200, help_text="The TARGET server's age public key (age1...).")


class DownloadLinkSerializer(serializers.Serializer):
    url = serializers.URLField()
    expires_at = serializers.DateTimeField()


def _move(pk):
    return get_object_or_404(SelfHostMoveRequest.objects.select_related("makerspace"), pk=pk)


class PlatformMoveListView(GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = PlatformMoveSerializer

    @extend_schema(tags=TAGS, summary="List every space's self-host move requests (newest first)",
                   responses={200: PlatformMoveSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        rows = SelfHostMoveRequest.objects.select_related("makerspace")
        if request.query_params.get("status") in SelfHostMoveRequest.Status.values:
            rows = rows.filter(status=request.query_params["status"])
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(PlatformMoveSerializer(page, many=True).data)


class _MoveAction(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]


class PlatformMoveDecisionView(_MoveAction):
    approve = True

    @extend_schema(tags=TAGS, summary="Decide a self-host move request", request=MoveDecisionSerializer,
                   responses={200: PlatformMoveSerializer, **errors(400, 401, 403, 404, 409, 423)})
    def post(self, request, pk):
        body = MoveDecisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        move = _move(pk)
        assert_write_allowed(move.makerspace_id)
        move = moves.decide(request.user, move, approve=self.approve, note=body.validated_data["note"])
        return Response(PlatformMoveSerializer(move).data)


class PlatformMoveRejectView(PlatformMoveDecisionView):
    approve = False


class PlatformMoveExportView(_MoveAction):
    @extend_schema(tags=TAGS, summary="Run the move export, encrypted to the target server's key",
                   request=ExportSerializer, responses={200: PlatformMoveSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        body = ExportSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        move = moves.start_export(request.user, _move(pk), body.validated_data["recipient"])
        return Response(PlatformMoveSerializer(move).data)


class PlatformMoveDiscardView(_MoveAction):
    @extend_schema(tags=TAGS, summary="Delete the move export file from this server", request=None,
                   responses={200: PlatformMoveSerializer, **errors(401, 403, 404, 423)})
    def post(self, request, pk):
        move = _move(pk)
        assert_write_allowed(move.makerspace_id)
        return Response(PlatformMoveSerializer(moves.discard_artifact(request.user, move)).data)


class PlatformMoveDownloadLinkView(_MoveAction):
    @extend_schema(tags=TAGS, summary="Issue a five-minute, one-use download link for the export",
                   request=None, responses={200: DownloadLinkSerializer, **errors(401, 403, 404)})
    def post(self, request, pk):
        move = _move(pk)
        if move.status != SelfHostMoveRequest.Status.EXPORTED or not move.artifact_path:
            return Response({"detail": "There is no export file to download."}, status=404)
        token = signing.dumps({"m": str(move.pk), "a": request.user.pk, "d": move.artifact_sha256}, salt=SALT)
        url = request.build_absolute_uri(reverse("selfhost-move-download", args=(move.pk, token)))
        return Response({"url": url, "expires_at": timezone.now() + timedelta(seconds=LINK_SECONDS)})


class SelfHostMoveDownloadView(APIView):
    """Consume a link from ``PlatformMoveDownloadLinkView``: signed, five minutes, one use."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=TAGS, summary="Download a move export through its one-use link", auth=[],
                   responses={(200, "application/octet-stream"): OpenApiResponse(
                       OpenApiTypes.BINARY, description="The age-encrypted move archive."),
                       404: OpenApiResponse(description="Invalid, used or expired link.")})
    def get(self, request, pk, token):
        from apps.accounts.models import User

        try:
            claims = signing.loads(token, salt=SALT, max_age=LINK_SECONDS)
        except signing.BadSignature:
            return Response({"detail": "The download link is invalid or expired."}, status=404)
        move = SelfHostMoveRequest.objects.select_related("makerspace").filter(pk=pk).first()
        actor = User.objects.filter(pk=claims.get("a"), is_active=True, is_superuser=True).first()
        if (move is None or actor is None or claims.get("m") != str(pk) or not move.artifact_path
                or claims.get("d") != move.artifact_sha256 or move.status != SelfHostMoveRequest.Status.EXPORTED):
            return Response({"detail": "The download link is invalid or expired."}, status=404)
        if not cache.add(f"{SALT}:{hashlib.sha256(token.encode()).hexdigest()}", 1, LINK_SECONDS):
            return Response({"detail": "This download link was already used."}, status=404)
        try:
            handle = open(move.artifact_path, "rb")
        except OSError:
            return Response({"detail": "The export file is no longer on this server."}, status=404)
        audit.record(actor, "selfhost_move.downloaded", makerspace=move.makerspace, target=move,
                     meta={"status": move.status, "artifact_sha256": move.artifact_sha256})
        response = FileResponse(handle, as_attachment=True, filename=f"{move.makerspace.slug}-move.tar.age",
                                content_type="application/octet-stream")
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


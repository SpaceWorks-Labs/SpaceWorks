"""The Space Manager's self-host move request and its status (release 2 L11, #128 C-23).

Request and status only: the superadmin approves and runs the export in /control/, and
nothing here exposes the archive, its location, the recipient key or a download.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.makerspaces.models import Makerspace

from .models_selfhost_move import SelfHostMoveRequest
from .selfhost_move import latest_request, request_move


class SelfHostMoveRequestSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SelfHostMoveRequest
        fields = ["id", "status", "status_label", "note", "requested_at", "decided_at", "decision_note",
                  "exported_at"]
        read_only_fields = fields


class SelfHostMoveStatusSerializer(serializers.Serializer):
    request = SelfHostMoveRequestSerializer(allow_null=True, help_text="The latest request, or null.")


class SelfHostMoveCreateSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class MoveErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)


ERRORS = {
    401: OpenApiResponse(MoveErrorSerializer, description="Not signed in."),
    403: OpenApiResponse(MoveErrorSerializer, description="Only the space's Space Manager (or the superadmin)."),
    404: OpenApiResponse(MoveErrorSerializer, description="No such makerspace."),
}


class SelfHostMoveRequestView(APIView):
    permission_classes = [IsActiveStaff]

    def _space(self, request, makerspace_id):
        require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        return get_object_or_404(Makerspace, pk=makerspace_id)

    @extend_schema(tags=["Tenant migration"], summary="Read this space's self-host move request status",
                   responses={200: SelfHostMoveStatusSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = self._space(request, makerspace_id)
        return Response(SelfHostMoveStatusSerializer({"request": latest_request(space)}).data)

    @extend_schema(
        tags=["Tenant migration"], summary="Ask the platform operator to move this space to its own server",
        request=SelfHostMoveCreateSerializer,
        responses={201: SelfHostMoveStatusSerializer, 400: OpenApiResponse(MoveErrorSerializer, description="Invalid note."),
                   409: OpenApiResponse(MoveErrorSerializer, description="move_request_exists: one is already open."),
                   **ERRORS})
    def post(self, request, makerspace_id):
        space = self._space(request, makerspace_id)
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(space.pk)
        serializer = SelfHostMoveCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        move = request_move(request.user, space, serializer.validated_data["note"])
        return Response(SelfHostMoveStatusSerializer({"request": move}).data, status=201)

"""Per-space restore API for the superadmin (owner decisions #110d, #111 Q1).

One flow for the React Backup & Restore panel and /control/: list a space's restore
points and restores, start a restore (preview is computed in the background), poll it,
confirm with recent re-authentication and the typed slug, or cancel before it applies.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.backup import space_restore_services as services
from apps.backup.models import MakerspaceRestoreOperation
from apps.backup.serializers_space_restore import (
    BackupScheduleSerializer,
    SpaceRestoreConfirmSerializer,
    SpaceRestoreCreateSerializer,
    SpaceRestoreSerializer,
)
from apps.backup.views_common import AUTH_ERRORS, NOT_FOUND, VALIDATION_ERROR
from apps.makerspaces.models import Makerspace

REAUTH = OpenApiResponse(description="Recent re-authentication is required (code reauthentication_required).")
TAGS = ["Backup"]


class SpaceRestoreListCreateView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="List a makerspace's restores", responses={
        200: SpaceRestoreSerializer(many=True), 404: NOT_FOUND, **AUTH_ERRORS})
    def get(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        rows = MakerspaceRestoreOperation.objects.filter(makerspace=space).select_related("makerspace")[:20]
        return Response(SpaceRestoreSerializer(rows, many=True).data)

    @extend_schema(tags=TAGS, summary="Start restoring a makerspace from one of its restore points",
                   description="Creates the restore and computes its preview in the background. Nothing "
                   "changes until the restore is confirmed.", request=SpaceRestoreCreateSerializer,
                   responses={202: SpaceRestoreSerializer, 400: VALIDATION_ERROR, 404: NOT_FOUND, **AUTH_ERRORS})
    def post(self, request, makerspace_id):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        serializer = SpaceRestoreCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        op = services.request_restore(request.user, space, serializer.validated_data["archive"])
        return Response(SpaceRestoreSerializer(op).data, status=status.HTTP_202_ACCEPTED)


class SpaceRestoreDetailView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Get a makerspace restore's preview, progress and report",
                   responses={200: SpaceRestoreSerializer, 404: NOT_FOUND, **AUTH_ERRORS})
    def get(self, request, restore_id):
        op = get_object_or_404(MakerspaceRestoreOperation.objects.select_related("makerspace"), pk=restore_id)
        return Response(SpaceRestoreSerializer(op).data)


class SpaceRestoreConfirmView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Confirm a previewed makerspace restore",
                   description="Requires recent re-authentication and the makerspace's slug. A safety "
                   "backup of the live space is taken first; the restore refuses if it fails.",
                   request=SpaceRestoreConfirmSerializer,
                   responses={202: SpaceRestoreSerializer, 400: VALIDATION_ERROR, 403: REAUTH, 404: NOT_FOUND})
    def post(self, request, restore_id):
        require_recent_reauth(request)
        op = get_object_or_404(MakerspaceRestoreOperation.objects.select_related("makerspace"), pk=restore_id)
        serializer = SpaceRestoreConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        op = services.confirm_restore(request.user, op, serializer.validated_data["confirm_slug"])
        return Response(SpaceRestoreSerializer(op).data, status=status.HTTP_202_ACCEPTED)


class SpaceRestoreAbortView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Cancel a makerspace restore before it applies", request=None,
                   responses={200: SpaceRestoreSerializer, 400: VALIDATION_ERROR, 404: NOT_FOUND, **AUTH_ERRORS})
    def post(self, request, restore_id):
        op = get_object_or_404(MakerspaceRestoreOperation.objects.select_related("makerspace"), pk=restore_id)
        return Response(SpaceRestoreSerializer(services.abort_restore(request.user, op)).data)


class BackupScheduleView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="One schedule view: the nightly platform and per-space backups",
                   responses={200: BackupScheduleSerializer, **AUTH_ERRORS})
    def get(self, request):
        from apps.backup.space_backup_schedule import schedule_overview
        return Response(BackupScheduleSerializer(schedule_overview()).data)

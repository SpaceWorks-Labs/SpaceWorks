"""Restore drills in the web superadmin console (#190, parity with /control/ Backup keys, drills and notices).

* read the latest drill reports and the drill settings;
* run a drill now for one space (its newest restorable archive), queued like the scheduled one;
* change the drill interval and the archive-ready notice, audited as ``backup.settings_updated``.

Key rotation itself (with the private key) stays on the server by design; the console only
says where to run it.
"""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

from .models import PlatformBackupSettings
from .models_drill import RestoreDrillReport
from .restore_drill import drills_configured, latest_restorable_archive

TAGS = ["Backup"]
KEY_ROTATION_HINT = "On the server: manage.py backup_keys (see docs/self-hosting.md, key rotation)."


class DrillConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "drill_unavailable"


class RestoreDrillReportSerializer(serializers.ModelSerializer):
    makerspace_id = serializers.IntegerField(source="makerspace_id_snapshot", read_only=True)
    makerspace_name = serializers.SerializerMethodField()

    class Meta:
        model = RestoreDrillReport
        fields = ("id", "makerspace_id", "makerspace_name", "started_at", "finished_at", "outcome", "error_code",
                  "checks")
        read_only_fields = fields

    def get_makerspace_name(self, obj) -> str | None:
        return obj.makerspace.name if obj.makerspace_id else None


class DrillSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformBackupSettings
        fields = ("restore_drill_interval_days", "archive_ready_notice_enabled")
        extra_kwargs = {
            "restore_drill_interval_days": {"min_value": 0, "max_value": 365,
                                            "help_text": "Days between drills of each space; 0 turns scheduled drills off."},
            "archive_ready_notice_enabled": {"help_text": "Email the superadmins when a requested archive is ready."},
        }


class DrillOverviewSerializer(serializers.Serializer):
    configured = serializers.BooleanField(help_text="False until this server has its restore identity and recipient.")
    settings = DrillSettingsSerializer()
    key_rotation = serializers.CharField(help_text="Where platform key rotation runs (server only, by design).")


class DrillRunSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField(min_value=1)


class DrillQueuedSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    archive_id = serializers.UUIDField()
    status = serializers.CharField()


class RestoreDrillListView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = RestoreDrillReportSerializer

    @extend_schema(tags=TAGS, summary="List restore drill reports (newest first)",
                   responses={200: RestoreDrillReportSerializer(many=True), **errors(401, 403)})
    def get(self, request):
        page = self.paginate_queryset(RestoreDrillReport.objects.select_related("makerspace"))
        return self.get_paginated_response(RestoreDrillReportSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Run a restore drill of one space now",
                   request=DrillRunSerializer, responses={202: DrillQueuedSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request):
        body = DrillRunSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        space = get_object_or_404(Makerspace, pk=body.validated_data["makerspace_id"])
        if not drills_configured():
            raise DrillConflict(gettext("Restore drills need this server's restore identity (TENANT_MIGRATION_AGE_*)."))
        archive = latest_restorable_archive(space.pk)
        if archive is None:
            raise DrillConflict(gettext("This space has no backup a drill can open yet. Back it up first."))
        from .tasks import run_restore_drill_now_task

        audit.record(request.user, "backup.drill_requested", makerspace=space, target=archive)
        run_restore_drill_now_task.delay(str(archive.pk), request.user.pk)
        return Response({"makerspace_id": space.pk, "archive_id": archive.pk, "status": "queued"},
                        status=status.HTTP_202_ACCEPTED)


class RestoreDrillSettingsView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=TAGS, summary="Read the restore drill settings",
                   responses={200: DrillOverviewSerializer, **errors(401, 403)})
    def get(self, request):
        return Response({"configured": drills_configured(), "key_rotation": KEY_ROTATION_HINT,
                         "settings": DrillSettingsSerializer(PlatformBackupSettings.load()).data})

    @extend_schema(tags=TAGS, summary="Change the drill interval and the archive-ready notice",
                   request=DrillSettingsSerializer, responses={200: DrillSettingsSerializer, **errors(400, 401, 403)})
    def patch(self, request):
        row = PlatformBackupSettings.load()
        body = DrillSettingsSerializer(row, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        changes = dict(body.validated_data)
        for field, value in changes.items():
            setattr(row, field, value)
        # Only these columns: a backup finishing meanwhile writes last_success_at on the same row.
        row.save(update_fields=[*changes, "updated_at"])
        audit.record(request.user, "backup.settings_updated", target=row, meta=changes)
        return Response(DrillSettingsSerializer(row).data)

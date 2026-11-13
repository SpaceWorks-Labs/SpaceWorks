"""Read-only "Last backup" line for a makerspace's managers (owner decision #111 Q2).

Space Managers no longer request or download archives; the superadmin backs up and
restores. A manager may still see when this makerspace was last covered by a
completed archive, so the line needs no module and changes no state.
"""

from django.db.models import Max
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.backup.models import BackupArchive, BackupRunCoverage, PlatformBackupSettings
from apps.backup.views_common import AUTH_ERRORS, NOT_FOUND
from apps.makerspaces.models import Makerspace


class MakerspaceBackupStatusSerializer(serializers.Serializer):
    last_backed_up_at = serializers.DateTimeField(
        allow_null=True,
        help_text="Newest completed archive covering this makerspace: its own archive, or the "
        "deployment archive a nightly run covered it with. Null when none exists yet.",
    )
    nightly_backups_enabled = serializers.BooleanField(
        help_text="Whether this deployment runs the nightly backup.",
    )


def last_backed_up_at(makerspace):
    """The newest completed archive that covers this makerspace, from existing backup rows."""
    own = BackupArchive.objects.filter(
        scope=BackupArchive.Scope.MAKERSPACE, makerspace=makerspace,
        status=BackupArchive.Status.AVAILABLE,
    ).aggregate(at=Max("completed_at"))["at"]
    covered = BackupRunCoverage.objects.filter(
        makerspace_id_snapshot=makerspace.pk, state=BackupRunCoverage.State.COVERED,
        archive__status=BackupArchive.Status.AVAILABLE,
    ).aggregate(at=Max("completed_at_snapshot"))["at"]
    return max((moment for moment in (own, covered) if moment is not None), default=None)


class MakerspaceBackupStatusView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Backup"],
        summary="Get when this makerspace was last backed up",
        responses={200: MakerspaceBackupStatusSerializer, 404: NOT_FOUND, **AUTH_ERRORS},
    )
    def get(self, request, makerspace_id):
        require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        makerspace = get_object_or_404(Makerspace, pk=makerspace_id)
        return Response(MakerspaceBackupStatusSerializer({
            "last_backed_up_at": last_backed_up_at(makerspace),
            "nightly_backups_enabled": PlatformBackupSettings.objects.filter(
                pk=1, automatic_backups_enabled=True).exists(),
        }).data)

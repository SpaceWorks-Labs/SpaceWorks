from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.backup.models import (
    BackupArchive,
    BackupArtifactComponent,
    BackupArtifactLedger,
    BackupLease,
    BackupRun,
    BackupRunCoverage,
    DeploymentRecoveryState,
    RestoreOperation,
    RestoreRollbackObject,
)
from apps.backup.models_host_identity import DeploymentDatabaseIdentity
from config.admin_access import SuperuserOnlyModelAdmin


class ReadOnlyBackupAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BackupArchive)
class BackupArchiveAdmin(ReadOnlyBackupAdmin):
    list_display = ("id", "scope", "makerspace", "status", "size_bytes", "created_at")
    list_filter = ("scope", "makerspace", "status", "created_at")
    search_fields = ("makerspace__name",)
    readonly_fields = tuple(field.name for field in BackupArchive._meta.fields)

    def get_urls(self):
        from django.urls import path
        return [path("notice/<str:token>/", self.admin_site.admin_view(self.notice_view),
                     name="backup_backuparchive_notice"), *super().get_urls()]

    def notice_view(self, request, token):
        """The signed link of the optional "archive ready" notice (#128 C-24): page only."""
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import redirect
        from django.urls import reverse
        from .operator_notice import archive_from_token
        archive_id = archive_from_token(token)
        if archive_id is None or not self.has_view_permission(request):
            raise PermissionDenied()
        return redirect(reverse("admin:backup_backuparchive_change", args=[archive_id]))


@admin.register(RestoreOperation)
class RestoreOperationAdmin(ReadOnlyBackupAdmin):
    list_display = ("id", "kind", "stage", "decision", "requested_at")
    list_filter = ("kind", "stage", "decision", "requested_at")
    readonly_fields = tuple(field.name for field in RestoreOperation._meta.fields)


for model in (
    DeploymentRecoveryState,
    BackupLease,
    BackupRun,
    BackupRunCoverage,
    RestoreRollbackObject,
    BackupArtifactLedger,
    BackupArtifactComponent,
    DeploymentDatabaseIdentity,
):
    admin.site.register(model, ReadOnlyBackupAdmin)


from apps.backup import admin_offsite  # noqa: E402,F401  (registers the offsite admins)

from . import admin_deployment  # noqa: E402,F401
from . import admin_keys  # noqa: E402,F401  (keys, drills and notices)

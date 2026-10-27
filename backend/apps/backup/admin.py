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
    readonly_fields = tuple(field.name for field in BackupArchive._meta.fields)


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

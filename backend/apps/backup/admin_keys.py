"""/control/: backup keys, archives on a retired key, restore drills and the operator notice.

Superadmin only. Every POST passes the /control/ re-authentication step-up first and
calls the same services as the host commands (``manage.py backup_keys``).
"""
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from apps.audit import services as audit

from .admin import ReadOnlyBackupAdmin
from .models import BackupArchive, PlatformBackupSettings
from .models_drill import RestoreDrillReport
from .models_keys import BackupKeyFingerprint


@admin.register(RestoreDrillReport)
class RestoreDrillReportAdmin(ReadOnlyBackupAdmin):
    list_display = ("started_at", "makerspace", "outcome", "error_code", "finished_at")
    list_filter = ("outcome", "started_at")
    readonly_fields = tuple(field.name for field in RestoreDrillReport._meta.fields)


@admin.register(BackupKeyFingerprint)
class BackupKeyFingerprintAdmin(RecentReauthenticationAdminMixin, ReadOnlyBackupAdmin):
    def get_urls(self):
        return [path("keys/", self.admin_site.admin_view(self.keys_view), name="backup_backupkeyfingerprint_keys"),
                *super().get_urls()]

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse("admin:backup_backupkeyfingerprint_keys"))

    def keys_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied()
        from .archive_reencrypt import can_reencrypt
        from .platform_key_rotation import Kind, current_fingerprint, stale_archives

        if request.method == "POST":
            response = self._recent_redirect(request)
            return response if response is not None else self._post(request)
        stale = [{"archive": row, "reencryptable": can_reencrypt(row)} for row in stale_archives()[:100]]
        return TemplateResponse(request, "admin/backup/keys.html", {
            **self.admin_site.each_context(request), "title": "Backup keys, drills and notices",
            "opts": self.model._meta, "stale": stale, "settings_row": PlatformBackupSettings.load(),
            "current": {kind.label: current_fingerprint(kind) for kind in Kind},
            "retired": BackupKeyFingerprint.objects.filter(retired_at__isnull=False)[:50],
            "drills": RestoreDrillReport.objects.select_related("makerspace")[:20],
        })

    def _post(self, request):
        from . import archive_reencrypt as reencrypt
        from .platform_key_rotation import record_rotation

        action = request.POST.get("action", "")
        try:
            require_recent_reauth(request)
            if action in {"rotate_platform", "rotate_server"}:
                result = record_rotation(request.user, action.removeprefix("rotate_"))
                self.message_user(request, f"Rotation recorded: {len(result['retired'])} key(s) retired, "
                                           f"{result['stale_archives']} archive(s) still on a retired key.")
            elif action in {"reencrypt", "purge"}:
                row = get_object_or_404(BackupArchive, pk=request.POST.get("archive_id"))
                (reencrypt.reencrypt_archive if action == "reencrypt" else reencrypt.purge_archive)(row, actor=request.user)
                self.message_user(request, "Archive re-encrypted." if action == "reencrypt" else "Archive purged.")
            elif action in {"reencrypt_all", "reencrypt_stop"}:
                self._request_reencryption(request, start=action == "reencrypt_all")
            elif action == "settings":
                self._save_settings(request)
        except (APIException, DjangoValidationError) as exc:
            self.message_user(request, str(getattr(exc, "detail", None) or exc), messages.ERROR)
        return redirect(reverse("admin:backup_backupkeyfingerprint_keys"))

    def _request_reencryption(self, request, *, start):
        PlatformBackupSettings.load()
        PlatformBackupSettings.objects.filter(pk=1).update(reencrypt_requested_at=timezone.now() if start else None)
        if start:
            audit.record(request.user, "backup.reencrypt_requested")
        else:
            audit.record(request.user, "backup.reencrypt_cancelled")
        if start:
            from .tasks import reencrypt_archives_task
            reencrypt_archives_task.delay()
        self.message_user(request, "Re-encryption started in the background." if start else "Re-encryption stopped.")

    def _save_settings(self, request):
        try:
            days = int(request.POST.get("restore_drill_interval_days", ""))
        except ValueError:
            days = -1
        if not 0 <= days <= 365:
            raise DjangoValidationError("Drill interval must be 0 (off) to 365 days.")
        notice = request.POST.get("archive_ready_notice_enabled") == "on"
        row = PlatformBackupSettings.load()
        row.restore_drill_interval_days, row.archive_ready_notice_enabled = days, notice
        row.save(update_fields=["restore_drill_interval_days", "archive_ready_notice_enabled", "updated_at"])
        audit.record(request.user, "backup.settings_updated", target=row,
                     meta={"restore_drill_interval_days": days, "archive_ready_notice_enabled": notice})
        self.message_user(request, "Saved.")

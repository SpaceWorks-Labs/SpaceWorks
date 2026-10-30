"""The /control/ "Backup & restore" page of one makerspace (owner decisions #111 Q1, SEAMLESS).

The same flow as the React panel, over the same services: one timeline of this space's
restore points (its own archives and the whole-platform archives that cover it), "Back up
now", then Restore -> preview -> confirm (recent re-authentication and the typed slug) ->
live progress. Every POST needs the /control/ re-authentication step-up.
"""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from rest_framework.exceptions import APIException

from apps.accounts.reauthentication import require_recent_reauth

from .models import BackupArchive, BackupRunCoverage, MakerspaceRestoreOperation
from . import space_restore_services as services


def restore_timeline(space):
    """Every restore point for one space, newest first, one shape for both scopes."""
    own = [{"archive": row, "scope": "space", "restorable": _restorable(row)}
           for row in services.restore_points(space)[:60]]
    covering = BackupRunCoverage.objects.filter(
        makerspace_id_snapshot=space.pk, state=BackupRunCoverage.State.COVERED,
        archive__status=BackupArchive.Status.AVAILABLE,
    ).select_related("archive").order_by("-completed_at_snapshot")[:30]
    platform = [{"archive": row.archive, "scope": "platform", "restorable": False} for row in covering]
    return sorted(own + platform, key=lambda item: item["archive"].completed_at, reverse=True)


def _restorable(row):
    from .serializers import BackupArchiveSerializer
    return BackupArchiveSerializer().get_restorable_in_app(row)


class MakerspaceBackupAdminMixin:
    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("<int:object_id>/backup/", view(self.backup_view), name="makerspaces_makerspace_backup"),
            path("<int:object_id>/backup/restores/<uuid:restore_id>/", view(self.space_restore_view),
                 name="makerspaces_makerspace_space_restore"),
            *super().get_urls(),
        ]

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None and obj.pk:
            fieldsets.append(("Backup and restore", {"fields": ("backup_summary",)}))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "backup_summary")

    @admin.display(description="Backups")
    def backup_summary(self, obj):
        if not obj or not obj.pk:
            return "Save this makerspace first."
        from .views_backup_status import last_backed_up_at
        last = last_backed_up_at(obj)
        url = reverse("admin:makerspaces_makerspace_backup", args=[obj.pk])
        return format_html('Last backup: {}. <a href="{}">Back up or restore this space</a>',
                           last or "never", url)

    def _space(self, request, object_id):
        space = self.get_object(request, str(object_id))
        if space is None or not self.has_view_permission(request, space):
            raise PermissionDenied()
        return space

    def backup_view(self, request, object_id):
        space = self._space(request, object_id)
        if request.method == "POST":
            response = self._recent_redirect(request)
            if response is not None:
                return response
            return self._backup_action(request, space)
        return TemplateResponse(request, "admin/backup/space_backup.html", {
            **self.admin_site.each_context(request), "title": f"Backup and restore: {space.name}",
            "space": space, "timeline": restore_timeline(space), "opts": self.model._meta,
            "restores": MakerspaceRestoreOperation.objects.filter(makerspace=space)[:10],
        })

    def _backup_action(self, request, space):
        action = request.POST.get("action")
        try:
            require_recent_reauth(request)
            if action == "backup_now":
                from .services import create_archive
                from .views_archives import _dispatch
                archive = create_archive(request.user, scope=BackupArchive.Scope.MAKERSPACE, makerspace=space)
                _dispatch(archive)
                self.message_user(request, "Backup started. It appears in the timeline when it completes.")
            elif action == "restore":
                archive = get_object_or_404(BackupArchive, pk=request.POST.get("archive_id"))
                op = services.request_restore(request.user, space, archive)
                return redirect(reverse("admin:makerspaces_makerspace_space_restore", args=[space.pk, op.pk]))
        except APIException as exc:
            self.message_user(request, _detail(exc), messages.ERROR)
        return redirect(reverse("admin:makerspaces_makerspace_backup", args=[space.pk]))

    def space_restore_view(self, request, object_id, restore_id):
        space = self._space(request, object_id)
        op = get_object_or_404(MakerspaceRestoreOperation, pk=restore_id, makerspace=space)
        if request.method == "POST":
            response = self._recent_redirect(request)
            if response is not None:
                return response
            try:
                require_recent_reauth(request)
                if request.POST.get("action") == "confirm":
                    services.confirm_restore(request.user, op, request.POST.get("confirm_slug", ""))
                elif request.POST.get("action") == "abort":
                    services.abort_restore(request.user, op)
            except APIException as exc:
                self.message_user(request, _detail(exc), messages.ERROR)
            return redirect(reverse("admin:makerspaces_makerspace_space_restore", args=[space.pk, op.pk]))
        return TemplateResponse(request, "admin/backup/space_restore.html", {
            **self.admin_site.each_context(request), "title": f"Restore {space.name}", "space": space,
            "op": op, "preview": op.preview, "report": op.report, "opts": self.model._meta,
            "refresh": op.stage in ("requested", "staging", "applying"),
        })


def _detail(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        detail = detail.get("detail") or next(iter(detail.values()), "")
    if isinstance(detail, list):
        detail = " ".join(str(item) for item in detail)
    return str(detail or exc)

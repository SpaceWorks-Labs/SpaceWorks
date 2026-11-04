"""Deployment facts and the /control/ backup console on the backup settings page.

The console is the one entry point of the SEAMLESS flow (#111): choose a scope -- the
whole platform or one space -- see that scope's restore points, back up now, and read the
one schedule view. A space scope opens that makerspace's Backup and restore page.
"""
import json

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from rest_framework.exceptions import APIException

from .admin import ReadOnlyBackupAdmin
from .models import BackupArchive, PlatformBackupSettings


@admin.register(PlatformBackupSettings)
class PlatformBackupSettingsAdmin(ReadOnlyBackupAdmin):
    readonly_fields = (*[field.name for field in PlatformBackupSettings._meta.fields], "deployment", "console")

    def get_urls(self):
        return [path("console/", self.admin_site.admin_view(self.console_view),
                     name="backup_platformbackupsettings_console"), *super().get_urls()]

    @admin.display(description="Deployment")
    def deployment(self, obj):
        from apps.operations.deployment_projection import deployment_projection
        return format_html("<pre>{}</pre>", json.dumps(deployment_projection(), indent=2, default=str))

    @admin.display(description="Backup and restore")
    def console(self, obj):
        return format_html('<a href="{}">Open the backup console</a>',
                           reverse("admin:backup_platformbackupsettings_console"))

    def console_view(self, request):
        from apps.makerspaces.servability import servable_queryset
        from .space_backup_schedule import schedule_overview

        scope = request.GET.get("scope", "platform")
        if scope.isdigit():
            return redirect(reverse("admin:makerspaces_makerspace_backup", args=[int(scope)]))
        if request.method == "POST":
            return self._backup_now(request)
        archives = BackupArchive.objects.filter(scope=BackupArchive.Scope.DEPLOYMENT,
                                                status=BackupArchive.Status.AVAILABLE).order_by("-completed_at")[:30]
        return TemplateResponse(request, "admin/backup/console.html", {
            **self.admin_site.each_context(request), "title": "Backup and restore",
            "spaces": servable_queryset().order_by("name"), "archives": archives,
            "schedule": schedule_overview(), "opts": self.model._meta,
        })

    def _backup_now(self, request):
        from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
        response = RecentReauthenticationAdminMixin()._recent_redirect(request)
        if response is not None:
            return response
        from .services import create_archive
        from .views_archives import _dispatch
        try:
            _dispatch(create_archive(request.user, scope=BackupArchive.Scope.DEPLOYMENT))
            self.message_user(request, "Whole-platform backup started.")
        except APIException as exc:
            self.message_user(request, str(getattr(exc, "detail", exc)), messages.ERROR)
        return redirect(reverse("admin:backup_platformbackupsettings_console"))

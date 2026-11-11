"""/control/ lists for the space controls (#185): schedules and announcements, read-only.

Writes go through the web console or the Makerspace list actions (``admin_actions``),
which call the same services; these lists only show what is set and allow cancelling.
"""

from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from config.admin_access import SuperuserOnlyModelAdmin

from . import announcements
from .models import PlatformAnnouncement, SpaceControlState
from django.utils.translation import gettext_lazy


class _ReadOnly(RecentReauthenticationAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SpaceControlState)
class SpaceControlStateAdmin(_ReadOnly):
    list_display = ("makerspace", "suspended_at", "read_only_at", "read_only_source", "archive_on", "purge_due_at")
    list_filter = ("read_only_source",)
    search_fields = ("makerspace__name", "makerspace__slug")
    readonly_fields = [field.name for field in SpaceControlState._meta.concrete_fields]


@admin.register(PlatformAnnouncement)
class PlatformAnnouncementAdmin(_ReadOnly):
    list_display = ("title", "severity", "audience", "starts_at", "ends_at", "send_email", "email_sent_at",
                    "cancelled_at")
    list_filter = ("severity", "audience")
    search_fields = ("title",)
    readonly_fields = [field.name for field in PlatformAnnouncement._meta.concrete_fields]
    actions = ["cancel_announcements"]

    @admin.action(description=gettext_lazy("Cancel selected announcements"))
    def cancel_announcements(self, request, queryset):
        for row in queryset:
            try:
                announcements.cancel(request.user, row.pk)
            except Exception as exc:  # typed 409 or authority refusal; shown, never a 500
                self.message_user(request, f"{row.title}: {exc}", level=messages.ERROR)
            else:
                self.message_user(request, f"Cancelled {row.title}.", level=messages.SUCCESS)

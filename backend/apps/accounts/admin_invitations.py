"""/control/ "People & roles": staff invitations, read-only (0.12.0).

Invitations are sent, re-sent, revoked and accepted in the web console (Staff & roles), whose
services bind the role and machine scope and audit each step. The invitee's address is stored
encrypted and never shown here; the token only as a digest, which is not shown either.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models_staff_invitations import StaffInvitation
from config.admin_display import badge
from config.admin_records import ControlRecordAdmin


@admin.register(StaffInvitation)
class StaffInvitationRecordAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "role", "state", "expires_at", "accepted_at", "revoked_at", "created_at")
    list_filter = ("role__legacy_role",)
    search_fields = ("makerspace__name", "role__name")
    list_select_related = ("makerspace", "role")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    @admin.display(description=_("State"))
    def state(self, obj):
        from django.utils import timezone

        if obj.accepted_at:
            return badge(_("Accepted"), "success")
        if obj.revoked_at:
            return badge(_("Revoked"), "danger")
        if obj.expires_at and obj.expires_at <= timezone.now():
            return badge(_("Expired"), "neutral")
        return badge(_("Waiting"), "warning")

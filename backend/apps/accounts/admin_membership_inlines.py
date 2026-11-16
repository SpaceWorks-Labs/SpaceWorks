"""Read-only membership inlines on the /control/ user page, one per track.

The default membership manager is community-only (one account per person), so a
person's staff-track rows get their own inline instead of disappearing from view.
"""

from unfold.admin import TabularInline

from apps.makerspaces.models import MakerspaceMembership

from .admin_staff_lifecycle import ReadOnlyMembershipInlineMixin


class MakerspaceMembershipInline(ReadOnlyMembershipInlineMixin, TabularInline):
    model = MakerspaceMembership
    fk_name = "user"
    fields = ("makerspace", "role")
    readonly_fields = fields
    autocomplete_fields = ("makerspace",)
    extra = 0
    verbose_name_plural = "Community memberships"


class StaffTrackMembershipInline(MakerspaceMembershipInline):
    verbose_name_plural = "Staff roles"

    def get_queryset(self, request):
        return MakerspaceMembership.staff_tracks.select_related("makerspace")

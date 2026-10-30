from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.accounts.admin_pii_masking import PiiMaskingAdminMixin
from apps.makerspaces.models import (
    MakerspaceMembership,
    MemberCard,
    MakerspaceWaiver,
    MemberProfile,
    MemberProject,
    MembershipRequest,
)
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(MakerspaceMembership)
class MakerspaceMembershipAdmin(PiiMaskingAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    # Actor snapshots carry a staff member's display name (#114: staff are masked too).
    pii_extra_fields = (
        "verified_actor_snapshot", "activated_actor_snapshot",
        "revoked_actor_snapshot", "witnessed_actor_snapshot",
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            from apps.accounts.models import User
            kwargs["queryset"] = User.objects.filter(account_kind="member")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["choices"] = [("custom", "Member")]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.user.account_kind == "staff":
            return tuple(field.name for field in self.model._meta.fields) + ("additional_role_names",)
        return super().get_readonly_fields(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.user.account_kind == "staff" and request.method not in {"GET", "HEAD"}:
            return False
        return super().has_change_permission(request, obj)
    list_display = ("user", "makerspace", "role", "created_at")
    list_filter = ("makerspace", "role")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user", "makerspace")
    readonly_fields = (
        "assigned_role", "additional_role_names",  # Written by role_membership_writes.
        "can_refer", "can_verify", "verified_at", "verified_by", "verified_actor_snapshot",
        "activated_actor_snapshot", "revoked_actor_snapshot",
        "waiver_accepted_at", "waiver_version_accepted", "accepted_waiver",
        "witnessed_at", "witnessed_waiver_version", "witnessed_waiver",
        "witnessed_by", "witnessed_actor_snapshot", "created_at",
    )

    @admin.display(description="Additional roles")
    def additional_role_names(self, obj):
        from apps.accounts.rbac_roles import membership_roles

        return ", ".join(role.name for role in membership_roles(obj)[1:]) or "—"


@admin.register(MakerspaceWaiver)
class MakerspaceWaiverAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("makerspace", "version", "is_active", "created_at", "superseded_at")
    readonly_fields = ("makerspace", "body", "version", "is_active", "created_by", "created_at", "superseded_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD") and super().has_change_permission(request, obj)


@admin.register(MembershipRequest)
class MembershipRequestAdmin(PiiMaskingAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    pii_extra_fields = ("invite_email",)
    list_display = ("makerspace", "kind", "state", "user", "invite_email", "created_at")
    readonly_fields = tuple(field.name for field in MembershipRequest._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD") and super().has_change_permission(request, obj)


@admin.register(MemberProfile)
class MemberProfileAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    """Read-only. A profile is the member's own writing, editable only by them.

    A superadmin needs to be able to SEE one — to answer a report about its content —
    but editing someone's self-description from the platform console would put words in
    their mouth. Removing it is the member's action or a `membership` purge.
    """

    list_display = ("membership", "is_visible", "github_username", "updated_at")
    list_filter = ("is_visible",)
    readonly_fields = tuple(field.name for field in MemberProfile._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD") and super().has_change_permission(request, obj)


@admin.register(MemberProject)
class MemberProjectAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("title", "profile", "position", "updated_at")
    readonly_fields = tuple(field.name for field in MemberProject._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD") and super().has_change_permission(request, obj)


@admin.register(MemberCard)
class MemberCardAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    """Read-only: issue/reissue/revoke are staff-console actions routed through the
    member-card services, and the photo is a private object with no admin preview."""

    list_display = ("makerspace", "card_number", "membership", "issued_at", "revoked_at", "print_count")
    list_filter = ("makerspace", ("revoked_at", admin.EmptyFieldListFilter))
    readonly_fields = tuple(field.name for field in MemberCard._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD") and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

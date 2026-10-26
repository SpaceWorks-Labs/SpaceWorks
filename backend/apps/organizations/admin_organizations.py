from django.contrib import admin
from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from django.db import transaction
from django.core.exceptions import PermissionDenied
from unfold.admin import ModelAdmin, TabularInline

from apps.audit import services as audit
from apps.organizations.models import (
    Organization,
    OrganizationMakerspace,
    OrganizationMembership,
)
from apps.organizations.governance import GOVERNANCE_ACTIONS
from apps.organizations.admin_errors import control_mutation
from config.admin_access import SuperuserOnlyModelAdmin


class OrganizationMakerspaceInline(TabularInline):
    model = OrganizationMakerspace
    fk_name = "organization"
    fields = ("makerspace", "relationship", "created_by", "created_at", "updated_at")
    readonly_fields = ("created_by", "created_at", "updated_at")
    autocomplete_fields = ("makerspace",)
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Organization)
class OrganizationAdmin(RecentReauthenticationAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("name", "slug", "legal_name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "legal_name", "registration_number")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_by", "created_at", "updated_at")
    inlines = (OrganizationMakerspaceInline,)

    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            from apps.organizations.services_governance import assert_deletable
            from apps.organizations.services_console import OrganizationConflict
            try:
                assert_deletable(obj)
            except OrganizationConflict:
                return False
        return super().has_delete_permission(request, obj=obj)

    def get_deleted_objects(self, objs, request):
        """Reject before the confirmation page renders, not after delete_queryset()."""
        from apps.organizations.services_governance import assert_deletable
        from apps.organizations.services_console import OrganizationConflict
        for obj in objs:
            try:
                assert_deletable(obj)
            except OrganizationConflict as exc:
                raise PermissionDenied(str(exc.detail)) from exc
        return super().get_deleted_objects(objs, request)

    @control_mutation
    def delete_model(self, request, obj):
        from apps.accounts.reauthentication import require_recent_reauth
        from apps.organizations.services_governance import delete_organization
        require_recent_reauth(request)
        delete_organization(obj, actor=request.user)

    @transaction.atomic
    @control_mutation
    def delete_queryset(self, request, queryset):
        from apps.accounts.reauthentication import require_recent_reauth
        from apps.organizations.services_governance import delete_organization
        require_recent_reauth(request)
        for obj in queryset.order_by("pk"):
            delete_organization(obj, actor=request.user)

    @control_mutation
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        # Django's admin LogEntry is a separate, unscoped store, so governance changes
        # need an entry in the project's append-only audit log too.
        audit.record(
            request.user,
            "organization.updated" if change else "organization.created",
            target=obj,
            meta={"slug": obj.slug},
        )


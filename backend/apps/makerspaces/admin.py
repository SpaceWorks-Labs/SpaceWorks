from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from apps.makerspaces.admin_governance import MakerspaceGovernanceMixin
from apps.makerspaces.admin_lifecycle_review import MakerspaceLifecycleReviewMixin
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.makerspaces.admin_capabilities import MakerspaceAdminForm, MakerspaceCapabilityAdminMixin
from apps.makerspaces.admin_images import MakerspaceImageAdminMixin
from apps.makerspaces.admin_owner import MakerspaceOwnerAdminMixin
from apps.makerspaces.admin_lifecycle_actions import MakerspaceLifecycleActionsMixin
from apps.makerspaces.admin_subdomains import SubdomainRequestAdmin
from apps.makerspaces.admin_archive_requests import MakerspaceArchiveRequestAdmin
from apps.makerspaces.admin_space_packs import SpacePackProfileAdmin  # noqa: F401
from apps.makerspaces.admin_imports import (  # noqa: F401
    ImportedUserReconciliationAdmin,
    PendingImportedMembershipAdmin,
)
from apps.makerspaces.domain_audit import record_control_save, record_domain_change
from apps.makerspaces.domain_verification import apply_domain_change
from apps.makerspaces.models import (
    Makerspace,
    MakerspaceMembership,
    normalize_frontend_domain,
)
from config.admin_access import SuperuserOnlyModelAdmin
from apps.accounts.admin_staff_lifecycle import ReadOnlyMembershipInlineMixin
from apps.makerspaces.admin_staff_accounts import MakerspaceStaffAccountAdminMixin


class ArchivedFilter(admin.SimpleListFilter):
    title = "archived"
    parameter_name = "archived"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(archived_at__isnull=False)
        if self.value() == "no":
            return queryset.filter(archived_at__isnull=True)
        return queryset


class MakerspaceMembershipInline(ReadOnlyMembershipInlineMixin, TabularInline):
    # Compatibility: intentionally writes only the legacy string; null FK = frozen fallback.
    model = MakerspaceMembership
    fk_name = "makerspace"
    fields = ("user", "role")
    readonly_fields = fields
    autocomplete_fields = ("user",)
    extra = 0



@admin.register(Makerspace)
class MakerspaceAdmin(
    RecentReauthenticationAdminMixin,
    MakerspaceGovernanceMixin,
    MakerspaceLifecycleReviewMixin,
    MakerspaceStaffAccountAdminMixin,
    MakerspaceOwnerAdminMixin,
    MakerspaceLifecycleActionsMixin,
    MakerspaceImageAdminMixin,
    MakerspaceCapabilityAdminMixin,
    SuperuserOnlyModelAdmin,
    ModelAdmin,
):
    form = MakerspaceAdminForm
    actions = ["archive_makerspaces", "unarchive_makerspaces", "purge_makerspaces",
               "approve_archive_requests", "decline_archive_requests"]
    list_display = (
        "name", "public_code", "slug", "location", "public_inventory_enabled",
        "frontend_domain", "hidden_from_central_directory", "frontend_mode",
        "lifecycle_state", "archived_at", "archive_request_status", "updated_at",
    )
    list_filter = ("public_inventory_enabled", ArchivedFilter)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "public_code", "slug", "location")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "create_staff_account_link",
                    "public_code",
                    "slug",
                    "location",
                    "public_inventory_enabled",
                    "public_site_enabled",
                    "public_landing_page",
                    "public_stats_enabled",
                    "public_stats_show_holder_names",
                    "frontend_domain",
                    "hidden_from_central_directory",
                    "default_loan_days",
                    "messaging_status",
                )
            },
        ),
        (
            "Capabilities",
            {"fields": ("capabilities",)},
        ),
        (
            "Public images",
            {
                "fields": (
                    "logo_preview",
                    "logo_upload",
                    "clear_logo",
                    "cover_preview",
                    "cover_upload",
                    "clear_cover",
                )
            },
        ),
    )
    readonly_fields = ("logo_preview", "cover_preview", "create_staff_account_link", "messaging_status")
    inlines = (MakerspaceMembershipInline,)

    @admin.display(description="Addressed messaging")
    def messaging_status(self, obj):
        from apps.integrations.messaging.settings_service import settings_payload
        if not obj.pk:
            return "Not configured"
        data = settings_payload(obj)
        return "; ".join(f"{channel}: {source}" for channel, source in data["effective_source"].items())

    def save_model(self, request, obj, form, change):
        previous_domain = None
        domain_changed = False
        if change and "frontend_domain" in form.changed_data:
            previous_domain = (
                type(obj).objects.only("frontend_domain").get(pk=obj.pk).frontend_domain
            )
            new_domain = normalize_frontend_domain(obj.frontend_domain)
            domain_changed = new_domain != previous_domain
            if domain_changed:
                # A superadmin edit is still a domain change: the new host must not
                # inherit the old host's VERIFIED trust on managed hosting.
                apply_domain_change(obj, new_domain)
        super().save_model(request, obj, form, change)
        if not change:
            self.assign_owner(request, obj, form)
        record_control_save(request.user, obj, form.changed_data, created=not change)
        if domain_changed:
            record_domain_change(request.user, obj, previous_domain)

    def has_delete_permission(self, request, obj=None):
        # The normal admin delete button is a permanent purge entry point. Keep it
        # object-scoped so the default bulk delete action stays disabled; bulk
        # purges must use the slug-confirming `purge_makerspaces` action below.
        if obj is None:
            return False
        return super().has_delete_permission(request, obj) and obj.archived_at is not None

    def get_deleted_objects(self, objs, request):
        # Django's stock collector asks every related ModelAdmin whether it can
        # delete each related object. Several of those admins intentionally
        # disable ordinary deletes to preserve history, which blocks a whole-space
        # purge even though lifecycle.purge() deletes the complete graph safely.
        objs = list(objs)
        from .admin_lifecycle_actions import visible_archive_impacts
        warnings = [
            f"Advisory unsettled charges for {row['object'].name}: {row['owned_pending']} owned pending, "
            f"{row['routed_pending']} routed pending, {row['total_pending']} total pending. Counts may change."
            for row in visible_archive_impacts(objs)
        ]
        return (
            [f"{self.opts.verbose_name}: {obj}" for obj in objs] + warnings,
            {self.opts.verbose_name_plural: len(objs)},
            set(),
            [],
        )

    def delete_model(self, request, obj):
        from apps.makerspaces import lifecycle

        lifecycle.purge(obj, request.user)

    @admin.display(boolean=True, description="Archived")
    def archived(self, obj):
        return obj.archived_at is not None

    @admin.display(description="Frontend mode")
    def frontend_mode(self, obj):
        return "single-tenant" if obj.frontend_domain else "central"


from apps.makerspaces.admin_memberships import (  # noqa: E402,F401
    MakerspaceMembershipAdmin,
    MakerspaceWaiverAdmin,
    MemberProfileAdmin,
    MemberProjectAdmin,
    MembershipRequestAdmin,
)

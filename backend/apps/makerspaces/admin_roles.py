"""/control/ "People & roles" and "Money": role definitions, extra roles and membership plans (0.12.0).

Read-only. Roles are fixed per space (decision 282: no custom roles; a staff member may hold
several), and every grant, extra role and plan change runs through the web console's services,
which validate the space, re-check authority and audit the change.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.makerspaces.models_additional_roles import MembershipAdditionalRole
from apps.makerspaces.models_membership_plans import MembershipPlan
from apps.makerspaces.models_roles import MakerspaceRole
from config.admin_display import membership_link
from config.admin_records import ControlRecordAdmin


@admin.register(MakerspaceRole)
class MakerspaceRoleRecordAdmin(ControlRecordAdmin):
    list_display = ("name", "makerspace", "legacy_role", "is_default", "is_protected", "action_count", "updated_at")
    list_filter = ("legacy_role", "is_default", "is_protected")
    search_fields = ("name", "slug", "makerspace__name")
    list_select_related = ("makerspace",)
    ordering = ("makerspace__name", "name")

    @admin.display(description=_("Actions allowed"))
    def action_count(self, obj):
        return len(obj.granted_actions or ())


@admin.register(MembershipAdditionalRole)
class MembershipAdditionalRoleRecordAdmin(ControlRecordAdmin):
    makerspace_lookup = "membership__makerspace_id"
    list_display = ("id", "membership_ref", "space", "role", "assigned_at")
    list_filter = ("role__legacy_role",)
    search_fields = ("role__name", "membership__makerspace__name")
    list_select_related = ("membership__makerspace", "role")
    ordering = ("-assigned_at",)

    @admin.display(description=_("Membership"), ordering="membership_id")
    def membership_ref(self, obj):
        return membership_link(obj, "membership")

    @admin.display(description=_("Space"), ordering="membership__makerspace__name")
    def space(self, obj):
        return obj.membership.makerspace


@admin.register(MembershipPlan)
class MembershipPlanRecordAdmin(ControlRecordAdmin):
    list_display = ("name", "makerspace", "plan_type", "interval", "amount", "currency", "is_active", "is_public",
                    "archived_at")
    list_filter = ("is_active", "is_public", "plan_type", "interval")
    search_fields = ("name", "slug", "makerspace__name")
    list_select_related = ("makerspace",)
    ordering = ("makerspace__name", "sort_order", "name")

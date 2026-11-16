"""/control/ "People & roles": per-machine and per-machine-type scope (decision 282), read-only.

A Machine Manager or Technician looks after the union of the machine types and individual
machines listed for their membership; nothing listed means nothing. Scope is granted, changed
and audited in the web console (staff grants and invitations), never here.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.machines.models_membership_scope import MembershipMachineScope, MembershipMachineTypeScope
from config.admin_display import membership_link
from config.admin_records import ControlRecordAdmin


class _ScopeAdmin(ControlRecordAdmin):
    makerspace_lookup = "membership__makerspace_id"
    ordering = ("-created_at",)

    @admin.display(description=_("Membership"), ordering="membership_id")
    def membership_ref(self, obj):
        return membership_link(obj, "membership")

    @admin.display(description=_("Space"), ordering="membership__makerspace__name")
    def space(self, obj):
        return obj.membership.makerspace


@admin.register(MembershipMachineTypeScope)
class MembershipMachineTypeScopeAdmin(_ScopeAdmin):
    list_display = ("id", "membership_ref", "space", "machine_type", "created_at")
    search_fields = ("machine_type__name", "membership__makerspace__name")
    list_select_related = ("membership__makerspace", "machine_type")


@admin.register(MembershipMachineScope)
class MembershipMachineScopeAdmin(_ScopeAdmin):
    list_display = ("id", "membership_ref", "space", "machine", "created_at")
    search_fields = ("machine__name", "membership__makerspace__name")
    list_select_related = ("membership__makerspace", "machine")

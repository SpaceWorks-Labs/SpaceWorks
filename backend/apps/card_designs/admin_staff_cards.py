"""/control/ "People & roles": staff ID cards, read-only (O-B4 part 2).

A staff card is issued, reissued and revoked in the web console (and ends automatically with the staff access),
never here. The list shows number, space, holder's membership and state; the verify token and wallet passes are
never shown.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.card_designs.models_staff_cards import StaffCard
from config.admin_display import membership_link
from config.admin_records import ControlRecordAdmin


@admin.register(StaffCard)
class StaffCardAdmin(ControlRecordAdmin):
    list_display = ("id", "number_text", "space", "membership_ref", "state", "issued_at", "print_count")
    list_filter = ("revoked_reason",)
    search_fields = ("number_text", "makerspace__name")
    list_select_related = ("makerspace", "membership")
    ordering = ("-issued_at",)

    @admin.display(description=_("Space"), ordering="makerspace__name")
    def space(self, obj):
        return obj.makerspace

    @admin.display(description=_("Membership"), ordering="membership_id")
    def membership_ref(self, obj):
        return membership_link(obj, "membership") if obj.membership_id else "-"

    @admin.display(description=_("State"), boolean=False)
    def state(self, obj):
        return _("Revoked") if obj.revoked_at else _("Live")

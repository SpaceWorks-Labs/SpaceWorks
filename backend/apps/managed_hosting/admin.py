"""/control/ read-only lists of the managed-hosting limiter (#187A); hidden while it is off.

Plans, assignments and invoices are changed in the web superadmin console (#190), whose
services audit every write; /control/ shows them for reference only.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin

from config.admin_access import SuperuserOnlyModelAdmin

from .availability import plans_enabled
from .models import HostingInvoice, HostingPlan, SpacePlanAssignment


class _ReadOnly(SuperuserOnlyModelAdmin, ModelAdmin):
    def has_module_permission(self, request):
        return plans_enabled() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return plans_enabled() and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HostingPlan)
class HostingPlanAdmin(_ReadOnly):
    list_display = ("name", "key", "is_active", "price_minor", "currency", "billing_period", "trial_days")
    readonly_fields = [field.name for field in HostingPlan._meta.concrete_fields]


@admin.register(SpacePlanAssignment)
class SpacePlanAssignmentAdmin(_ReadOnly):
    list_display = ("makerspace", "plan", "trial_ends_at", "trial_expired_at", "assigned_at")
    readonly_fields = [field.name for field in SpacePlanAssignment._meta.concrete_fields]


@admin.register(HostingInvoice)
class HostingInvoiceAdmin(_ReadOnly):
    list_display = ("number", "makerspace_name", "amount_minor", "currency", "due_on", "status", "paid_at")
    list_filter = ("status",)
    search_fields = ("number", "makerspace_name")
    readonly_fields = [field.name for field in HostingInvoice._meta.concrete_fields]

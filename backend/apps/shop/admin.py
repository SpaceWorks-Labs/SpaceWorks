"""/control/ "Shop": what each space sells, its orders, returns and stock, read-only (0.12.0).

Selling, collecting, returning and restocking run in the web console through the shop services
(stock locks, the core payments ledger and the audit trail). Buyer names, contact details and
pickup codes are never shown here.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.separability.tombstones import app_is_tombstoned
from apps.shop.models_catalogue import ShopProduct, ShopSettings
from apps.shop.models_orders import ShopOrder, ShopOrderReturn
from apps.shop.models_stock import ShopStockMovement
from config.admin_display import record_link, status_badge
from config.admin_records import ControlRecordAdmin


class ShopProductAdmin(ControlRecordAdmin):
    list_display = ("name", "makerspace", "kind", "category", "is_active", "is_public", "members_only", "archived_at")
    list_filter = ("is_active", "is_public", "kind", "members_only")
    search_fields = ("name", "slug", "category", "makerspace__name")
    list_select_related = ("makerspace",)
    ordering = ("makerspace__name", "sort_order", "name")


class ShopOrderAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "channel", "status_label", "total", "amount_due", "currency", "created_at",
                    "paid_at", "collected_at")
    list_filter = ("status", "channel", "currency")
    search_fields = ("makerspace__name",)
    list_select_related = ("makerspace",)
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    status_label = status_badge("status")


class ShopOrderReturnAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "order_ref", "quantity", "disposition", "amount", "created_at")
    list_filter = ("disposition",)
    search_fields = ("makerspace__name",)
    list_select_related = ("makerspace",)
    ordering = ("-created_at",)
    hidden_fields = ("reason",)

    @admin.display(description=_("Order"), ordering="order_id")
    def order_ref(self, obj):
        return record_link(obj, "order", _("Order #%(id)s"), "admin:shop_shoporder_change")


class ShopStockMovementAdmin(ControlRecordAdmin):
    list_display = ("id", "makerspace", "variant", "kind", "quantity", "balance_after", "reason", "created_at")
    list_filter = ("kind",)
    search_fields = ("variant__product__name", "reason", "makerspace__name")
    list_select_related = ("makerspace", "variant", "variant__product")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"


class ShopSettingsAdmin(ControlRecordAdmin):
    list_display = ("makerspace", "online_hold_minutes", "desk_hold_hours", "returns_window_days",
                    "uncollected_cancel_days", "updated_at")
    search_fields = ("makerspace__name",)
    list_select_related = ("makerspace",)
    ordering = ("makerspace__name",)


# Registered rather than decorated, so a tombstoned shop leaves no screens (separability).
if not app_is_tombstoned("shop"):
    admin.site.register(ShopProduct, ShopProductAdmin)
    admin.site.register(ShopOrder, ShopOrderAdmin)
    admin.site.register(ShopOrderReturn, ShopOrderReturnAdmin)
    admin.site.register(ShopStockMovement, ShopStockMovementAdmin)
    admin.site.register(ShopSettings, ShopSettingsAdmin)

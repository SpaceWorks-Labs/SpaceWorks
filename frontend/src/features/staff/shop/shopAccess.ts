import { t } from "@lingui/core/macro";
import { capabilityOn } from "../../../lib/features";

type Space = { enabled_modules?: string[]; enabled_features?: string[] };

/**
 * Mirrors the backend's implied actions: `manage_shop` includes selling and reading, and the
 * Space Manager (`manage_makerspace`) holds all three. The server still decides every call.
 */
export function shopAccess(actions: readonly string[], isSuperadmin: boolean, space: Space) {
  const has = (action: string) => isSuperadmin || actions.includes(action);
  const manage = has("manage_shop") || has("manage_makerspace");
  const sell = manage || has("sell_shop");
  const view = sell || has("view_shop");
  const on = (key: string) => capabilityOn(space, key);
  return {
    manage, sell, view,
    features: {
      tax: on("shop.tax"), returns: on("shop.returns"), cashUp: on("shop.cash_up"), memberPrices: on("shop.member_prices"),
      orderLimits: on("shop.order_limits"), bundles: on("shop.bundles"), consumableLink: on("shop.consumable_link"),
      receipts: on("shop.receipts"), publicStock: on("shop.public_stock"), reorder: on("shop.reorder"),
      // #135 Q-S18: event merch rides on event pickup, which itself needs the Events module.
      eventOffers: on("shop.event_pickup") && (space.enabled_modules ?? []).includes("events"),
    },
  };
}
export type ShopAccess = ReturnType<typeof shopAccess>;

export type ShopView = "orders" | "pos" | "cash" | "catalogue" | "events" | "stock" | "reports" | "settings";

/** Sub-views the actor may open, in the order the tab lists them. Gated views are omitted, never disabled. */
export function shopViews(access: ShopAccess): { key: ShopView; label: string }[] {
  return [
    access.view ? { key: "orders" as const, label: t`Orders` } : null,
    access.sell ? { key: "pos" as const, label: t`Till` } : null,
    access.sell && access.features.cashUp ? { key: "cash" as const, label: t`Cash-up` } : null,
    access.manage ? { key: "catalogue" as const, label: t`Catalogue` } : null,
    access.manage && access.features.eventOffers ? { key: "events" as const, label: t`Event merch` } : null,
    access.view ? { key: "stock" as const, label: t`Stock` } : null,
    access.manage ? { key: "reports" as const, label: t`Reports` } : null,
    access.manage ? { key: "settings" as const, label: t`Settings` } : null,
  ].filter((view): view is { key: ShopView; label: string } => view !== null);
}

import type { RouteCase } from "./source.census-D12";
import type { Phase } from "./fetch.census-D12";

// These registry paths also serve single-tenant domains. On the CENTRAL portal
// they have neither a :slug nor a selected tenant. The production query's
// enabled condition explicitly refuses to fetch; inventing a tenant here would
// exercise a different route/context. Scoped and single variants stay counted.
// `notice`: the exact sentence the contextless variant shows instead of a false empty list or a blank
// detail (decision 592); the exempt branch asserts it is visible.
const ORDERS_NOTICE = "Open your orders from a makerspace's member area.";
export const CONTEXTLESS: readonly { screen: string; source: string; guard: string; notice?: string; noticeSource?: string }[] = [
  { screen: "MemberEventTicketPage", source: "features/events/MemberEventTicketPage.tsx", guard: "identity.data?.id && makerspaceId",
    notice: "Open your ticket from a makerspace's member area." },
  { screen: "MemberOrdersPage", source: "features/events/ticketing/MemberOrdersPage.tsx", guard: "Boolean(space.makerspaceId)", notice: ORDERS_NOTICE },
  { screen: "MemberSeriesPassPage", source: "features/events/ticketing/MemberSeriesPassPage.tsx", guard: "Boolean(space.makerspaceId && id)",
    notice: "Buy series passes from a makerspace's events page." },
  { screen: "MemberShopOrdersPage", source: "features/members/shopOrders/MemberShopOrdersPage.tsx", guard: "Boolean(space.makerspaceId)", notice: ORDERS_NOTICE,
    noticeSource: "features/events/ticketing/MemberOrdersPage.tsx" },
  { screen: "EventAddonPage", source: "features/events/eventAddons/MemberEventAddonRoutes.tsx", guard: "!space.makerspaceId", notice: "This event page is unavailable here." },
  { screen: "PrizesPage", source: "features/events/eventAddons/MemberEventAddonRoutes.tsx", guard: "!makerspaceId", notice: "Prizes are unavailable here." },
  { screen: "DonatePage", source: "features/donations/DonatePage.tsx", guard: "Boolean(slug) && giving", notice: "Give from a makerspace's own donation page." },
];
const reasons: Record<Phase, string> = {
  loading: "There is no selected makerspace, so the explicit resource-query guard cannot start a request.",
  empty: "There is no selected makerspace collection; the unscoped shell is distinct from the independently tested scoped empty list.",
  error: "No tenant request is sent from this context, so there is no failed tenant operation to retry.",
  permission: "No tenant request is sent; this shell cannot infer or request authority in an arbitrary space.",
  module: "No selected tenant has a module state; scoped and single-tenant variants test the actual module refusal.",
};
export function contextlessExemption(row: RouteCase, phase: Phase) {
  const contract = CONTEXTLESS.find(item => item.screen === row.screen);
  // Shop order detail uses its account-owned ID without a selected tenant.
  // Its parent list query can be disabled while that detail still fetches.
  const shopDetail = row.screen === "MemberShopOrdersPage" && row.pattern.includes(":orderId");
  return row.mode === "central" && !row.pattern.includes(":slug") && !shopDetail && contract
    ? `${contract.source} (${contract.guard}): ${reasons[phase]}` : undefined;
}
/** The exact unavailable-here sentence of a contextless variant, when its screen decides one. */
export function contextlessNotice(row: RouteCase, phase: Phase) {
  return contextlessExemption(row, phase) ? CONTEXTLESS.find(item => item.screen === row.screen)?.notice : undefined;
}

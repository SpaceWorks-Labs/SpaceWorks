import { t } from "@lingui/core/macro";
import type { QueryClient } from "@tanstack/react-query";
import type { StaffRole } from "./rolesApi";

export type MembershipRoles = {
  role_ids: number[];
  roles: Pick<StaffRole, "id" | "slug" | "name">[];
};

export function assignableRoles(roles: StaffRole[], actions: readonly string[], isSuperadmin: boolean) {
  if (isSuperadmin) return roles;
  const ceiling = new Set(actions.filter((action) => action !== "manage_makerspace"));
  return roles.filter((role) => !role.granted_actions.includes("manage_makerspace")
    && role.granted_actions.every((action) => ceiling.has(action)));
}

export function refreshMembershipAuthority(client: QueryClient, msId: number) {
  return Promise.all([
    ["staff", "memberships", msId], ["staff", "roles", msId],
    ["members", msId], ["member-machine-scope", msId], ["staff", "me"],
    // Role and machine-type changes narrow or widen what the machine, dashboard and
    // to-buy views return, including the actor's own when they edit themselves.
    ["machines"], ["machine-types"], ["machine-service-requests"], ["machine-service-handover"],
    ["dashboard"], ["dashboard-print-queue"], ["dashboard-maintenance-queue"], ["procurement"],
  ].map((queryKey) => client.invalidateQueries({ queryKey })));
}

/** One line per fixed role, keyed by slug; shown in the role picker and the Roles reference. */
export const ROLE_DESCRIPTIONS: Record<string, string> = {
  space_manager: t`Manages this makerspace, its staff, settings and all workflows.`,
  inventory_manager: t`Manages inventory and the full hardware loan lifecycle.`,
  machine_manager: t`Manages machines and service work within this person's assigned machine types.`,
  event_manager: t`Manages events and registrations, event reports and email templates.`,
  booking_manager: t`Manages bookable spaces, bookings, booking rules, reports and email templates.`,
  handover: t`Issues accepted requests and direct handouts, processes returns and hands over completed machine jobs.`,
  technician: t`Works the repair jobs assigned to them, runs scheduled maintenance and marks machines, items and rooms in or out of service within their coverage. No inventory, money or settings.`,
  shop_manager: t`Runs the shop: products, stock, prices, orders, the front desk, cash-ups, returns, shop reports and the shop's own settings. No other inventory, money or settings.`,
  fundraising: t`Runs donations: campaigns, gifts, regular givers, sponsors, donor list and receipts. No other money, and the non-profit profile stays the Space Manager's.`,
  member: t`Uses member services without staff management access.`,
};

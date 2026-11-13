import type { ModuleKey } from "../../../lib/retiredModules";

/**
 * Which staff actions make a role a user of a module. The server has no such table: a module is a
 * whole capability and the routes inside it each check their own action, so this lists the actions
 * those routes require (apps/accounts/rbac_actions.py names). An empty list means the module has no
 * staff action of its own and is shown for the Space Manager only. Typed by the generated
 * ModulesEnum (minus retired keys), so a newly registered module is a type error until it is mapped here.
 */
export const MODULE_ACTIONS: Record<ModuleKey, readonly string[]> = {
  public_inventory: ["view_inventory"], request_workflow: ["accept_request", "reject_request", "issue_request"],
  staff_admin: ["view_inventory", "edit_inventory"], guest_handover: ["issue_request", "issue_direct_loan", "return_request"],
  scanner: ["assign_box", "issue_request", "return_request"], telegram: [],
  evidence_uploads: ["upload_evidence"], qr_management: ["manage_qr"], bulk_import: ["edit_inventory"],
  containers: ["edit_inventory", "assign_box"], stock_transfers: ["transfer_stock"], stocktake: ["edit_inventory"],
  reports: ["view_audit", "view_finance"], qr_print_batches: ["manage_qr"], asset_units: ["manage_qr", "edit_inventory"],
  machines: ["manage_machines", "work_repairs", "run_maintenance", "set_service_state"],
  machine_service: ["manage_machines", "collect_service_request", "manage_printing"], events: ["manage_events"],
  event_reimbursements: ["manage_events", "record_reimbursement_payout"], bookings: ["manage_bookings"],
  membership: ["manage_members", "manage_member_cards", "scan_member_cards", "manage_member_units"],
  notifications: [], email: [], sms: [], whatsapp: [], slack: [], mattermost: [], discord: [], webhook: [],
  payments: ["view_finance", "record_payment", "manage_donations"], member_accounts: ["manage_members"],
  mobile: [], devices: ["manage_devices"], presence: ["manage_members"],
  shop: ["manage_shop", "sell_shop", "view_shop"], analytics: ["view_analytics"],
};

/** What holding one action also grants (mirrors IMPLIED_ACTIONS in rbac_actions.py, the parts that reach modules). */
const IMPLIED: Record<string, readonly string[]> = {
  manage_machines: ["manage_printing", "collect_service_request"], manage_member_cards: ["scan_member_cards"],
  manage_members: ["manage_member_cards", "scan_member_cards", "view_member_units"],
  manage_shop: ["sell_shop", "view_shop"], sell_shop: ["view_shop"],
};

/** What the signed-in member (no staff action) meets in each area of the member app and public pages. */
export const MEMBER_MODULES: ReadonlySet<string> = new Set<ModuleKey>([
  "public_inventory", "request_workflow", "events", "bookings", "membership", "member_accounts", "notifications",
  "payments", "shop", "mobile", "presence", "email",
]);

export type RoleLike = { slug: string; name: string; granted_actions: string[] };

function held(role: RoleLike): Set<string> {
  const all = new Set(role.granted_actions);
  for (const action of [...all]) for (const implied of IMPLIED[action] ?? []) all.add(implied);
  return all;
}

/** Space Manager (and anyone holding manage_makerspace) runs the whole space. */
export const runsWholeSpace = (role: RoleLike) => role.slug === "space_manager" || role.granted_actions.includes("manage_makerspace");

export function roleUsesModule(role: RoleLike, key: string): boolean {
  if (runsWholeSpace(role)) return true;
  if (role.slug === "member") return MEMBER_MODULES.has(key);
  const actions = held(role);
  return (MODULE_ACTIONS[key as ModuleKey] ?? []).some(action => actions.has(action));
}

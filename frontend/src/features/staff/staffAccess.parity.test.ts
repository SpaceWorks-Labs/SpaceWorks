import { describe, expect, it } from "vitest";
import { getStaffAccess } from "./staffAccess";

// The full grantable set the backend sends as `superadmin_actions` (rbac.ROLE_GRANTABLE_ACTIONS).
const SUPERADMIN = ["accept_request", "assign_box", "collect_service_request", "edit_inventory", "issue_direct_loan", "issue_request",
  "manage_bookings", "manage_devices", "manage_events", "manage_machines", "manage_makerspace", "manage_member_cards", "manage_members",
  "manage_printing", "manage_qr", "record_payment", "record_reimbursement_payout", "reject_request", "return_request", "scan_member_cards",
  "upload_evidence", "view_audit", "view_finance", "view_inventory"];
// Tabs that belong to the signed-in PERSON, not to the space: a staff account's own delivery
// channels, events it personally organizes, organization governance analytics and resource
// grants. Their endpoints are targetless or per-account, so no space switch can show them.
const PERSON_SCOPED = new Set(["channels", "organized", "organization-analytics", "granted"]);
const SPACE_MANAGER_SETS = [
  SUPERADMIN,
  ["manage_makerspace", "view_inventory", "edit_inventory", "accept_request", "reject_request", "assign_box", "issue_request",
    "issue_direct_loan", "return_request", "upload_evidence", "manage_qr", "manage_printing", "manage_machines", "manage_devices",
    "manage_events", "manage_bookings", "manage_members", "manage_member_cards", "scan_member_cards", "view_finance",
    "record_payment", "view_audit", "collect_service_request"],
];

describe("#115 console parity: the superadmin sees every Space-Manager tab", () => {
  it.each([false, true])("in a chosen space (single-tenant %s)", singleTenantLocked => {
    const superadmin = new Set(getStaffAccess(SUPERADMIN, true, singleTenantLocked).allowedTabs);
    for (const actions of SPACE_MANAGER_SETS) {
      const missing = getStaffAccess(actions, false, singleTenantLocked).allowedTabs
        .filter(tab => !PERSON_SCOPED.has(tab) && !superadmin.has(tab));
      expect(missing).toEqual([]);
    }
  });

  it("keeps the platform tabs too", () => {
    const tabs = getStaffAccess(SUPERADMIN, true, false).allowedTabs;
    for (const tab of ["platform-dashboard", "platform", "modules", "migration", "organizations"]) expect(tabs).toContain(tab);
  });
});

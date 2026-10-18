// Tenant Space Manager actions needed by navigation tests. Platform operators
// have a separate route allowlist and cannot stand in for this staff account.
export const spaceManagerActions = [
  "manage_makerspace", "manage_members", "view_inventory", "edit_inventory",
  "accept_request", "issue_direct_loan", "manage_qr", "view_audit",
  "manage_machines", "manage_events", "manage_bookings", "manage_devices",
  "view_finance",
] as const;

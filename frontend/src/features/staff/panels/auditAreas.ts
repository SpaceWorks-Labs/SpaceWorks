import { t } from "@lingui/core/macro";

/**
 * Audit areas (owner decision 219(e)). Twin of `backend/apps/audit/areas.py`
 * AREA_ACTIONS / REPAIR_SUBJECT_ACTIONS / TECHNICIAN_ACTIONS; the server stays the
 * authority and narrows every row it returns, so this only decides which area filters
 * and which copy the audit page offers.
 */
export const AUDIT_AREAS = [
  "lending", "handover", "machines", "events", "bookings", "shop", "repairs", "finance", "donations", "people", "platform",
] as const;
export type AuditArea = (typeof AUDIT_AREAS)[number];

export const AUDIT_AREA_ACTIONS: Record<Exclude<AuditArea, "repairs">, readonly string[]> = {
  lending: ["edit_inventory", "accept_request", "reject_request", "manage_qr"],
  handover: ["assign_box", "issue_request", "issue_direct_loan", "return_request", "upload_evidence"],
  machines: ["manage_machines", "manage_printing"],
  events: ["manage_events"],
  bookings: ["manage_bookings"],
  shop: ["manage_shop"],
  finance: ["view_finance"],
  donations: ["manage_donations"],
  people: ["manage_members"],
  platform: ["manage_makerspace"],
};
// A subject-area manager or a Technician may hold repair rows; the server decides which.
export const AUDIT_REPAIR_ACTIONS = [
  "manage_machines", "edit_inventory", "manage_bookings", "work_repairs", "run_maintenance", "set_service_state",
];

// #219(e-1): twin of `areas.READER_ACTIONS`. Any of these admits the audit log and the
// audit reports WITHOUT `view_audit` (narrowed to the reader's areas); handover-desk
// actions alone do not. Every other `view_audit` gate is unchanged.
export const AUDIT_READER_ACTIONS: readonly string[] = [...new Set([
  ...Object.entries(AUDIT_AREA_ACTIONS).filter(([area]) => area !== "handover").flatMap(([, actions]) => actions),
  "work_repairs", "run_maintenance", "set_service_state",
])];

/** Whether these effective actions may open the audit log at all. */
export function canReadAudit(actions: readonly string[]): boolean {
  return actions.includes("view_audit") || AUDIT_READER_ACTIONS.some(action => actions.includes(action));
}

/** The areas these effective actions open, or `null` for the whole space. */
export function auditAreasFor(actions: readonly string[] | undefined): AuditArea[] | null {
  if (!actions || actions.includes("manage_makerspace")) return null;
  return AUDIT_AREAS.filter(area => (area === "repairs" ? AUDIT_REPAIR_ACTIONS : AUDIT_AREA_ACTIONS[area])
    .some(action => actions.includes(action)));
}

export function auditAreaLabel(area: string): string {
  const labels: Record<AuditArea, string> = {
    lending: t`Inventory`, handover: t`Handover desk`, machines: t`Machines and printing`,
    events: t`Events`, bookings: t`Bookings`, shop: t`Shop`, repairs: t`Repairs and maintenance`,
    finance: t`Money`, donations: t`Donations and sponsors`, people: t`Members and people`, platform: t`Settings, security and platform`,
  };
  return labels[area as AuditArea] ?? area;
}

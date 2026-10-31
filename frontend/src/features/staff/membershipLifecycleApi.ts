import { staffRequest } from "../../lib/api";

// Hand-written mirrors of the release-2 L4 staff routes (`admin_api/urls_membership_lifecycle.py`).
// Swap for `src/generated/api.ts` types once the schema snapshot is regenerated at merge.

export type Standing = "upcoming" | "active" | "ending_soon" | "grace" | "ended" | "lapsed" | "cancelled" | "no_term";

export type WorklistRow = {
  id: number; name: string; email: string; member_number: string; pii_masked?: boolean;
  desk: { term_id: number; plan_id: number; plan_name: string; ends_at: string; grace_ends_at: string;
    standing: Standing; renewal_payment_status: string; reminded_today: boolean };
};
export type RegisterRow = {
  member_number: string; name: string; email: string; plan: string; standing: Standing;
  term_ends_at: string | null; source: string; joined_at: string; pii_masked?: boolean;
};
export type MemberTitle = { id: number; name: string; colour: string; sort_order: number; archived_at: string | null };
export type TitleAssignment = { id: number; title: MemberTitle; is_primary: boolean; created_at: string };
export type InviteLink = {
  id: number; label: string; plan: number | null; plan_name: string; max_uses: number; uses: number;
  expires_at: string | null; revoked_at: string | null; live: boolean; created_at: string; code?: string;
};
export type MemberRecord = { state_code: string; gstin: string; staff_notes: string; source: string; member_number: string; pii_masked?: boolean };
export type TimelineEntry = { at: string; kind: string; text: string; plan: string; until: string | null; lifetime: boolean; reason: string };
export type ConsentRow = { id: number; purpose: string; notice_version: string; source: string; given_at: string; withdrawn_at: string | null };
export type ErasureRow = { id: number; membership: number; member_name: string; member_email: string; status: string;
  member_note: string; decision_note: string; created_at: string; decided_at: string | null };
export type ImportPreviewRow = { row: number; action: "create" | "update" | "skip"; reason: string; data: Record<string, unknown> };
export type ImportPreview = { headers: string[]; mapping: Record<string, string>; suggested_mapping: Record<string, string>;
  counts: { create: number; update: number; skip: number }; rows: ImportPreviewRow[]; total_rows: number };
export type ImportResultRow = { row: number; action: string; reason: string; status: string; email: string };
export type ImportResult = { batch_id: number; counts: Record<string, number>; rows: ImportResultRow[] };
export type FinancialYear = { financial_year_start_month: number; current_label: string; current_start: string; current_end: string;
  presets: { key: string; label: string; start: string; end: string }[] };
export type ReportPayload = { rows: (string | number | null)[][]; meta?: Record<string, unknown> };
export type SummaryStatus = { enabled: boolean; next_run_at: string | null; opted_out: boolean };

const space = (id: number) => `/admin/makerspaces/${id}`;
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const lifecycleKeys = {
  worklist: (id: number) => ["membership-l4", id, "worklist"] as const,
  register: (id: number, standing: string) => ["membership-l4", id, "register", standing] as const,
  titles: (id: number) => ["membership-l4", id, "titles"] as const,
  invites: (id: number) => ["membership-l4", id, "invites"] as const,
  erasure: (id: number) => ["membership-l4", id, "erasure"] as const,
  imported: (id: number) => ["membership-l4", id, "imported"] as const,
  summary: (id: number) => ["membership-l4", id, "summary"] as const,
  financialYear: (id: number) => ["membership-l4", id, "financial-year"] as const,
  member: (membershipId: number, part: string) => ["membership-l4", "member", membershipId, part] as const,
};

export const lifecycleApi = {
  worklist: (id: number) => staffRequest<WorklistRow[]>(`${space(id)}/renewal-worklist`),
  remind: (id: number, membershipIds: number[]) =>
    staffRequest<{ sent: number[]; skipped: number[] }>(`${space(id)}/renewal-reminders`, json("POST", { membership_ids: membershipIds })),
  extend: (membershipId: number, input: { reason: string; days?: number; until?: string }) =>
    staffRequest(`/admin/memberships/${membershipId}/extend`, json("POST", input)),
  register: (id: number, standing: string) =>
    staffRequest<RegisterRow[]>(`${space(id)}/member-register${standing ? `?standing=${encodeURIComponent(standing)}` : ""}`),
  titles: (id: number) => staffRequest<MemberTitle[]>(`${space(id)}/membership-titles`),
  createTitle: (id: number, input: Partial<MemberTitle>) => staffRequest<MemberTitle>(`${space(id)}/membership-titles`, json("POST", input)),
  archiveTitle: (titleId: number) => staffRequest<MemberTitle>(`/admin/membership-titles/${titleId}`, { method: "DELETE" }),
  invites: (id: number) => staffRequest<InviteLink[]>(`${space(id)}/membership-invite-links`),
  createInvite: (id: number, input: { label: string; plan_id: number | null; max_uses: number; expires_at: string | null }) =>
    staffRequest<InviteLink>(`${space(id)}/membership-invite-links`, json("POST", input)),
  revokeInvite: (linkId: number) => staffRequest<InviteLink>(`/admin/membership-invite-links/${linkId}/revoke`, { method: "POST" }),
  bulkDecide: (id: number, requestIds: number[], decision: "approve" | "reject", reason = "") =>
    staffRequest<{ id: number; ok: boolean; code: string }[]>(`${space(id)}/join-requests/bulk-decide`,
      json("POST", { request_ids: requestIds, decision, reason })),
  erasure: (id: number) => staffRequest<ErasureRow[]>(`${space(id)}/erasure-requests`),
  decideErasure: (requestId: number, decision: "approve" | "reject", note: string) =>
    staffRequest<ErasureRow>(`/admin/erasure-requests/${requestId}/${decision}`, json("POST", { note })),
  importStep: (id: number, step: "preview" | "apply", body: FormData) =>
    staffRequest<ImportPreview | ImportResult>(`${space(id)}/members/import/${step}`, { method: "POST", body }),
  summary: (id: number) => staffRequest<SummaryStatus>(`${space(id)}/membership-summary`),
  setSummary: (id: number, input: { enabled?: boolean; opted_out?: boolean }) =>
    staffRequest<SummaryStatus>(`${space(id)}/membership-summary`, json("PUT", input)),
  financialYear: (id: number) => staffRequest<FinancialYear>(`${space(id)}/financial-year`),
  report: (id: number, key: string, params: Record<string, string>) =>
    staffRequest<ReportPayload>(`/admin/makerspace/${id}/analytics/${key}?${new URLSearchParams(params)}`),
  setFinancialYear: (id: number, month: number) =>
    staffRequest<FinancialYear>(`${space(id)}/financial-year`, json("PUT", { financial_year_start_month: month })),
  record: (membershipId: number) => staffRequest<MemberRecord>(`/admin/memberships/${membershipId}/record`),
  saveRecord: (membershipId: number, input: Partial<MemberRecord>) =>
    staffRequest<MemberRecord>(`/admin/memberships/${membershipId}/record`, json("PUT", input)),
  memberTitles: (membershipId: number) => staffRequest<TitleAssignment[]>(`/admin/memberships/${membershipId}/titles`),
  assignTitle: (membershipId: number, titleId: number, primary: boolean) =>
    staffRequest<TitleAssignment[]>(`/admin/memberships/${membershipId}/titles`, json("POST", { title_id: titleId, primary })),
  unassignTitle: (membershipId: number, titleId: number) =>
    staffRequest<TitleAssignment[]>(`/admin/memberships/${membershipId}/titles/${titleId}`, { method: "DELETE" }),
  history: (membershipId: number) => staffRequest<TimelineEntry[]>(`/admin/memberships/${membershipId}/history`),
  consents: (membershipId: number) => staffRequest<ConsentRow[]>(`/admin/memberships/${membershipId}/consents`),
};

export const STANDING_LABELS: Record<Standing, string> = {
  upcoming: "Upcoming", active: "Active", ending_soon: "Ending soon", grace: "In grace", ended: "Ended",
  lapsed: "Lapsed", cancelled: "Cancelled", no_term: "No term",
};

export function standingTone(standing: Standing): "success" | "warn" | "danger" | "neutral" | "info" {
  if (standing === "active") return "success";
  if (standing === "ending_soon" || standing === "grace") return "warn";
  if (standing === "lapsed" || standing === "cancelled") return "danger";
  if (standing === "upcoming") return "info";
  return "neutral";
}

/** A CSV the browser can save: quotes every cell, doubles embedded quotes. */
export function toCsv(rows: Record<string, unknown>[], columns: string[]) {
  const cell = (value: unknown) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  return [columns.map(cell).join(","), ...rows.map((row) => columns.map((column) => cell(row[column])).join(","))].join("\n");
}

/** A report's matrix (header row first) as one object per row. */
export function reportRecords(payload?: ReportPayload) {
  const [header, ...rows] = payload?.rows ?? [];
  return rows.map((row) => Object.fromEntries((header ?? []).map((key, index) => [String(key), row[index]])));
}

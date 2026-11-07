import { t } from "@lingui/core/macro";
import type { QueryClient } from "@tanstack/react-query";

import { API_V1_URL, StructuredApiError, staffRequest } from "../../lib/api";

/** Shapes of the lane L5 finance routes (kept local until the generated client catches up). */
export type FinanceAccess = {
  everything: boolean; domains: string[]; machine_type_ids: number[] | null;
  record_domains: string[]; record_everything: boolean;
};
export type SummaryRow = {
  month: string; domain: string; machine_type: string; currency: string; income: string; other_income: string;
  refunds: string; expenses: string; payouts: string; money_in: string; money_out: string; net: string;
};
export type LedgerEntry = {
  id: number; kind: "receipt" | "expense"; domain: string; machine_type_id: number | null; machine_type_label: string;
  event_id: number | null; category: string; method: string; account: "cash" | "bank"; amount: string;
  currency: string; entry_date: string; description: string; counterparty: string; reference: string;
  source_kind: string; source_id: string; has_receipt: boolean; receipt_kind?: "pdf" | "image" | ""; created_at: string; voided_at: string | null;
  void_reason: string;
};
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type Claim = {
  id: number; payment_id: number; subject_label: string; method: string; reference: string; paid_on: string;
  amount: string; currency: string; status: string; decision_note: string; decided_at: string | null;
  created_at: string; via_pay_link: boolean;
};
export type Confirmation = {
  id: number; payment_id: number; subject_label: string; method: string; reference: string; received_at: string;
  amount: string; currency: string; status: string; decision_note: string; created_at: string;
  decided_at: string | null; proposed_by_me: boolean; from_claim: boolean;
};
export type CaptureFlag = {
  id: number; payment_id: number; subject_label: string; kind: "late" | "duplicate" | "mismatch"; provider: string;
  captured_amount: string | null; captured_currency: string; charge_amount: string; charge_currency: string;
  prior_status: string; flagged_at: string; resolution: string; resolution_note: string;
};
export type Dispute = {
  id: number; payment_id: number; subject_type: string; subject_label: string; provider: string; amount: string;
  currency: string; reason: string; status: "open" | "under_review" | "won" | "lost" | "closed";
  provider_status: string; evidence_due_at: string | null; opened_at: string;
};
export type EventMoney = {
  event_id: number; event: string; currency: string; income: string; refunds: string; other_income: string;
  expenses: string; payouts: string; budget: string | null; budget_left: string | null; net: string;
};

export const DOMAIN_LABELS: Record<string, string> = {
  inventory: t`Inventory`, loans: t`Lending`, machines: t`Machines`, bookings: t`Bookings and rooms`, events: t`Events`,
  membership: t`Membership`, donations: t`Donations and sponsors`, shop: t`Shop`, general: t`General`,
};
export const EXPENSE_CATEGORIES = ["to_buy", "repair", "maintenance", "consumables", "reimbursement", "prize", "rent",
  "utilities", "equipment", "salaries", "software", "events", "other_expense"] as const;
export const RECEIPT_CATEGORIES = ["donation", "grant", "sponsorship", "interest", "venue_fee", "other_income"] as const;
export const METHODS = ["cash", "upi", "bank_transfer", "card", "cheque", "online", "other"] as const;

export function words(value: string) {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const space = (id: number) => `/admin/makerspace/${id}`;
const post = (body?: unknown): RequestInit => ({ method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const financeKeys = {
  access: (id: number) => ["finance-access", id] as const,
  summary: (id: number, from: string, to: string) => ["finance-summary", id, from, to] as const,
  entries: (id: number, params: string) => ["finance-entries", id, params] as const,
  claims: (id: number, status: string) => ["paid-claims", id, status] as const,
  confirmations: (id: number) => ["settlement-confirmations", id] as const,
  flags: (id: number) => ["capture-flags", id] as const,
  disputes: (id: number) => ["disputes", id] as const,
};

export const financeApi = {
  access: (id: number) => staffRequest<FinanceAccess>(`${space(id)}/finance/access`),
  summary: (id: number, from: string, to: string) =>
    staffRequest<{ start: string; end: string; rows: SummaryRow[] }>(
      `${space(id)}/finance/summary?${new URLSearchParams({ from, to })}`),
  entries: (id: number, params: string) => staffRequest<Page<LedgerEntry>>(`${space(id)}/finance/entries?${params}`),
  createEntry: (id: number, body: Record<string, unknown>) => staffRequest<LedgerEntry>(`${space(id)}/finance/entries`, post(body)),
  voidEntry: (id: number, entry: number, reason: string) =>
    staffRequest<LedgerEntry>(`${space(id)}/finance/entries/${entry}/void`, post({ reason })),
  receiptUrl: (id: number, entry: number) => staffRequest<{ url: string }>(`${space(id)}/finance/entries/${entry}/receipt-url`),
  receiptUpload: (id: number, contentType: string, size: number) =>
    staffRequest<{ evidence_id: number; upload_url: string; fields: Record<string, string>; method?: string;
      headers?: Record<string, string> }>(`${space(id)}/finance/receipt-upload`, post({ content_type: contentType, size_bytes: size })),
  claims: (id: number, status: string) => staffRequest<Page<Claim>>(`${space(id)}/paid-claims${status ? `?status=${status}` : ""}`),
  decideClaim: (id: number, claim: number, decision: "confirm" | "reject", note = "") =>
    staffRequest<Claim>(`${space(id)}/paid-claims/${claim}/${decision}`, post(decision === "reject" ? { note } : undefined)),
  confirmations: (id: number) => staffRequest<Page<Confirmation>>(`${space(id)}/settlements`),
  decideConfirmation: (id: number, row: number, decision: "confirm" | "reject", note = "") =>
    staffRequest<Confirmation>(`${space(id)}/settlements/${row}/${decision}`, post(decision === "reject" ? { note } : undefined)),
  flags: (id: number) => staffRequest<Page<CaptureFlag>>(`${space(id)}/capture-flags`),
  resolveFlag: (id: number, flag: number, body: { resolution: string; note?: string }) =>
    staffRequest<CaptureFlag>(`${space(id)}/capture-flags/${flag}/resolve`, post(body)),
  disputes: (id: number) => staffRequest<Page<Dispute>>(`${space(id)}/disputes`),
  eventMoney: (id: number, event: number) => staffRequest<EventMoney[]>(`${space(id)}/finance/events/${event}`),
  setBudget: (id: number, event: number, currency: string, amount: string) =>
    staffRequest(`${space(id)}/finance/events/${event}/budget`, { method: "PUT", body: JSON.stringify({ currency, amount }) }),
  payLink: (id: number, payment: number, email: string) =>
    staffRequest<{ url: string; expires_at: string; emailed: boolean }>(`${space(id)}/payments/${payment}/pay-link`,
      post({ email })),
};

/** Upload one receipt (photo or PDF) to the staging key the server presigned; returns the evidence id. */
export async function uploadReceipt(makerspaceId: number, file: File) {
  const grant = await financeApi.receiptUpload(makerspaceId, file.type, file.size);
  let response: Response;
  if (grant.method === "PUT") {
    response = await fetch(grant.upload_url, { method: "PUT", headers: grant.headers, body: file });
  } else {
    const form = new FormData();
    Object.entries(grant.fields).forEach(([key, value]) => form.append(key, value));
    form.append("file", file);
    response = await fetch(grant.upload_url, { method: "POST", body: form });
  }
  if (!response.ok) throw new Error(t`The receipt upload failed. Try again.`);
  return grant.evidence_id;
}

export function invalidateFinance(client: QueryClient, id: number) {
  for (const key of ["finance-summary", "finance-entries", "paid-claims", "settlement-confirmations", "capture-flags"]) {
    void client.invalidateQueries({ queryKey: [key, id] });
  }
  void client.invalidateQueries({ queryKey: ["staff-payments"] });
}

/** Account-less pay-link page calls: plain fetch, no session and no publishable key. */
export async function payLinkRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_V1_URL}/public/pay/${path}`, {
    ...init, headers: { "Content-Type": "application/json" },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new StructuredApiError(response.status, body);
  return body as T;
}

export function financeError(error: unknown) {
  if (error instanceof StructuredApiError) {
    if (error.status === 403) return t`You don't have access to this money.`;
    return error.detail || error.message;
  }
  return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
}

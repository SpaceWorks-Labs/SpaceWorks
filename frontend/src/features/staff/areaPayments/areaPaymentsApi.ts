import { t } from "@lingui/core/macro";

import { StructuredApiError, staffRequest } from "../../../lib/api";
import type { Paginated } from "../../../lib/usePaginatedQuery";
import { FINANCE_ONLY, SUBJECT_ACTION } from "../paymentAccess";
import type { PaymentRow } from "../paymentsApi";

/**
 * Decision 242(a)(b): the own-area Payments queue (`apps/payments/views_area_queue.py`). The server
 * returns only charges the caller owns by subject authority; donations never reach an area manager.
 * Settling and waiving reuse the existing mark-offline / waive routes in `paymentsApi`.
 */
export const AREA_KEYS = ["lending", "machines", "events", "bookings", "shop", "membership", "general"] as const;
export type AreaKey = (typeof AREA_KEYS)[number];

/** Decision 247: the `lending` key is shown as "Inventory"; keys and routes stay unchanged. */
export const AREA_LABELS: Record<AreaKey, string> = {
  lending: t`Inventory`,
  machines: t`Machines`,
  events: t`Events`,
  bookings: t`Bookings`,
  shop: t`Shop`,
  membership: t`Membership`,
  general: t`Other`,
};

export const areaLabel = (key: string) => AREA_LABELS[key as AreaKey] ?? key;
export const isAreaKey = (key: string): key is AreaKey => (AREA_KEYS as readonly string[]).includes(key);

/** Mirrors `finance_scope.PAYMENT_DOMAINS` through `area_queue.area_of` (loans/inventory -> lending). */
export const SUBJECT_AREA: Record<string, AreaKey> = {
  machine_service_request: "machines", machine_session: "machines", booking: "bookings",
  event_registration: "events", event_order: "events", event_venue_fee: "events", submission_fee: "events",
  team_registration: "events", event_deposit: "events", shop_order: "shop",
  loan_deposit: "lending", loan_late_fee: "lending", loan_rental: "lending", loan_damage: "lending", loan_lost: "lending",
  makerspace_membership: "membership", membership_term: "membership", membership_term_start: "membership",
  membership_request: "membership", guest_pass: "membership",
};

/** The areas whose charges the actor owns; finance staff own every area (`owned_subject_types` None). */
export function ownedAreas(actions: readonly string[], everything: boolean): AreaKey[] {
  if (everything) return [...AREA_KEYS];
  const owned = new Set(Object.entries(SUBJECT_ACTION).filter(([subject, action]) => !FINANCE_ONLY.has(subject)
    && actions.includes(action)).map(([subject]) => SUBJECT_AREA[subject]).filter(Boolean));
  return AREA_KEYS.filter(key => owned.has(key));
}

export type AreaQueueRow = PaymentRow & { area: AreaKey; member_id: number | null };
export type AreaGroup = { area: AreaKey; pending: number; overdue: number; claims: number; owed: Record<string, string> };
export type AreaClaim = {
  id: number; payment_id: number; subject_label: string; method: string; reference: string; paid_on: string;
  amount: string; currency: string; status: string; decision_note: string; decided_at: string | null;
  created_at: string; via_pay_link: boolean;
};
export type AreaPayLink = { url: string; expires_at: string; emailed: boolean };
export type QueueFilters = { area?: string; status?: string; subject_type?: string; due_state?: string; ordering?: string; page?: number };

const base = (makerspaceId: number) => `/admin/makerspace/${makerspaceId}/payments`;
const post = (body?: unknown): RequestInit => ({ method: "POST", ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

export function areaQueuePath(makerspaceId: number, filters: QueueFilters) {
  const query = new URLSearchParams();
  for (const key of ["area", "status", "subject_type", "due_state", "ordering"] as const) {
    if (filters[key]) query.set(key, filters[key]!);
  }
  if (filters.page && filters.page > 1) query.set("page", String(filters.page));
  const suffix = query.toString();
  return `${base(makerspaceId)}/area-queue${suffix ? `?${suffix}` : ""}`;
}

export const areaKeys = {
  // Under ["payments", id] so `invalidatePaymentViews` refreshes the queue after every settle or waive.
  list: (id: number, filters: QueueFilters) => ["payments", id, "area-queue", filters] as const,
  summary: (id: number) => ["payments", id, "area-summary"] as const,
  claims: (id: number, area = "") => ["payments", id, "area-claims", area] as const,
};

export const areaPaymentsApi = {
  list: (id: number, filters: QueueFilters) => staffRequest<Paginated<AreaQueueRow>>(areaQueuePath(id, filters)),
  summary: (id: number) => staffRequest<{ groups: AreaGroup[] }>(`${base(id)}/area-queue/summary`),
  claims: (id: number, area?: string) => staffRequest<Paginated<AreaClaim>>(`${base(id)}/area-queue/claims${area ? `?area=${encodeURIComponent(area)}` : ""}`),
  confirmClaim: (id: number, claim: number) => staffRequest<AreaClaim>(`${base(id)}/area-queue/claims/${claim}/confirm`, post()),
  rejectClaim: (id: number, claim: number, note: string) =>
    staffRequest<AreaClaim>(`${base(id)}/area-queue/claims/${claim}/reject`, post({ note })),
  payLink: (id: number, payment: number, email: string) =>
    staffRequest<AreaPayLink>(`${base(id)}/${payment}/area-pay-link`, post({ email })),
  reminder: (id: number, payment: number) => staffRequest<PaymentRow>(`${base(id)}/${payment}/area-reminder`, post()),
};

// Plain wording for the codes the queue's actions can return (decision 235).
const AREA_ERRORS: Record<string, string> = {
  settlement_awaiting_confirmation: t`A payment for this charge is already waiting for a second person to confirm it.`,
  self_confirmation: t`You recorded this payment, so someone else must confirm it.`,
  settlement_decided: t`Someone already decided this payment. The list has been refreshed.`,
  reminder_no_recipient: t`This person has no email address on their account, so no reminder can be sent.`,
  payment_terminal: t`This charge is no longer waiting for payment.`,
  pay_link_has_account: t`This charge belongs to an account. Send a reminder instead; they sign in to pay.`,
  pay_link_not_staff_raised: t`Pay links are only for charges your team raised by hand.`,
};

/** A readable sentence for a refused queue action: known codes first, then the server's own detail. */
export function areaErrorText(error: unknown) {
  if (error instanceof StructuredApiError) {
    if (error.code && AREA_ERRORS[error.code]) return AREA_ERRORS[error.code];
    if (error.status === 403) return t`You can't do this for this charge. Ask your Space Manager if it should be yours.`;
    if (error.status === 404) return t`This charge is not in your queue any more. The list has been refreshed.`;
    return error.detail || error.message;
  }
  return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
}

/** Owed per currency, never summed across currencies: "USD 12.00 · INR 300.00". */
export function owedText(owed: Record<string, string>, format: (amount: string, currency: string) => string) {
  const entries = Object.entries(owed);
  return entries.length ? entries.map(([currency, amount]) => format(amount, currency)).join(" · ") : "";
}

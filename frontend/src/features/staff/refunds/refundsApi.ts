import { plural, t } from "@lingui/core/macro";
import type { QueryClient } from "@tanstack/react-query";

import type {
  RefundCase, RefundCaseListResponse, RefundCaseStatusEnum, RefundPolicy,
} from "../../../generated/api";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import { invalidatePaymentViews, type RefundReceipt } from "../paymentsApi";

export type { RefundCase, RefundPolicy };

// A case records what a member MAY be owed. Money only moves on approve; the queue is
// therefore a decision list, newest first, with the open ones as the default view.
export const CASE_STATUS_TABS: ReadonlyArray<readonly [RefundCaseStatusEnum | "", string]> = [
  ["open", "To decide"], ["approval_failed", "Provider refused"], ["approved", "Approved"],
  ["declined", "Declined"], ["", "All"],
];

export const CASE_STATUS_LABELS: Record<RefundCaseStatusEnum, string> = {
  open: t`To decide`, approved: t`Approved`, approval_failed: t`Provider refused`,
  declined: t`Declined`, withdrawn: t`Withdrawn`, void: t`Closed`,
};

export const REASON_LABELS: Record<RefundCase["reason_code"] | "capture_flagged", string> = {
  event_cancelled: t`Event cancelled by the space`, registration_cancelled: t`Registration cancelled`,
  booking_cancelled: t`Booking cancelled`, staff_cancelled: t`Cancelled by staff`,
  membership_cancelled: t`Membership term cancelled`,
  member_request: t`Member asked`,
  fee_waived: t`Loan fee waived`,
  capture_flagged: t`Unexpected online payment`,
  order_unfulfilled: t`Order could not be seated`,
  ticket_type_changed: t`Changed to a cheaper ticket`,
  pass_occurrence_cancelled: t`Pass occurrence cancelled`,
  donation_returned: t`Gift returned to the giver`,
  submission_disqualified: t`Project disqualified`,
  team_rejected: t`Team rejected`,
  price_drop: t`Price lowered after payment`,
  job_cancelled: t`Prepaid job cancelled before it started`,
  quote_difference: t`Job cost less than its prepaid quote`,
  shop_return: t`Shop items returned`,
  shop_uncollected: t`Shop order not collected`,
  shop_unfulfilled: t`Shop order could not be filled`,
  // Hack-money (#180): G2 withdrawal and shortlist refunds, G10 deposits returned after the event.
  submission_withdrawn: t`Project withdrawn`,
  not_shortlisted: t`Team not shortlisted`,
  deposit_returned: t`Deposit returned after the event`,
};

export function caseTone(status: RefundCaseStatusEnum): "success" | "warn" | "danger" | "neutral" {
  if (status === "approved") return "success";
  if (status === "open") return "warn";
  if (status === "approval_failed") return "danger";
  return "neutral";
}

export function refundCaseKey(makerspaceId: number, status: string, page: number) {
  return ["refund-cases", makerspaceId, status, page] as const;
}

export function listRefundCases(makerspaceId: number, status: string, page: number) {
  const query = new URLSearchParams({ page: String(page) });
  if (status) query.set("status", status);
  return staffRequest<RefundCaseListResponse>(`/admin/makerspace/${makerspaceId}/refund-cases?${query}`);
}

export type ApproveBody = { amount?: string; reason?: string; note?: string; receipt?: RefundReceipt; keep_membership?: boolean;
  /** Parity C18 (`events.refund_cancels_tickets`): also cancel the tickets an event charge paid for. */
  cancel_tickets?: boolean };

/** Charges whose approval may also cancel tickets: a ticket order or a paid registration. */
export const EVENT_TICKET_SUBJECTS: ReadonlySet<string> = new Set(["event_order", "event_registration"]);

export function approveRefundCase(makerspaceId: number, caseId: number, body: ApproveBody) {
  return staffRequest<RefundCase>(`/admin/makerspace/${makerspaceId}/refund-cases/${caseId}/approve`, {
    method: "POST", body: JSON.stringify(body),
  });
}

export function declineRefundCase(makerspaceId: number, caseId: number, note: string) {
  return staffRequest<RefundCase>(`/admin/makerspace/${makerspaceId}/refund-cases/${caseId}/decline`, {
    method: "POST", body: JSON.stringify({ note }),
  });
}

export function refundPolicyKey(makerspaceId: number) {
  return ["refund-policies", makerspaceId] as const;
}

export function listRefundPolicies(makerspaceId: number) {
  return staffRequest<RefundPolicy[]>(`/admin/makerspace/${makerspaceId}/refund-policies`);
}

export type PolicyBody = Pick<RefundPolicy, "full_before_minutes" | "partial_before_minutes" | "partial_percent"
  | "cancellation_fee" | "full_within_days" | "partial_mode">;

export function saveRefundPolicy(makerspaceId: number, area: RefundPolicy["area"], body: PolicyBody) {
  return staffRequest<RefundPolicy>(`/admin/makerspace/${makerspaceId}/refund-policies/${area}`, {
    method: "PUT", body: JSON.stringify(body),
  });
}

export function removeRefundPolicy(makerspaceId: number, area: RefundPolicy["area"]) {
  return staffRequest<void>(`/admin/makerspace/${makerspaceId}/refund-policies/${area}`, { method: "DELETE" });
}

/** A membership plan's own rule; without one the plan follows the membership default. */
export function savePlanPolicy(makerspaceId: number, planId: number, body: PolicyBody) {
  return staffRequest<RefundPolicy>(`/admin/makerspace/${makerspaceId}/refund-policies/membership/plans/${planId}`, {
    method: "PUT", body: JSON.stringify(body),
  });
}

export function removePlanPolicy(makerspaceId: number, planId: number) {
  return staffRequest<void>(`/admin/makerspace/${makerspaceId}/refund-policies/membership/plans/${planId}`, { method: "DELETE" });
}

/** A decision changes the case list AND the payment ledger (a refund line appears). */
export function invalidateRefundViews(queryClient: QueryClient, makerspaceId: number) {
  queryClient.invalidateQueries({ queryKey: ["refund-cases", makerspaceId] });
  queryClient.invalidateQueries({ queryKey: ["operations-report", "refunds"] });
  invalidatePaymentViews(queryClient, makerspaceId);
}

const CASE_ERRORS = (): Record<string, string> => ({
  refund_case_closed: t`Someone already decided this refund. The list has been refreshed.`,
  refund_exceeds_balance: t`That is more than is left to refund on this charge.`,
  refund_rail_unavailable: t`Online refunds are switched off on this deployment. Decline the case and return the money another way.`,
  refund_receipt_required: t`Record how the money was returned: method, reference and date.`,
  refund_amount_invalid: t`Enter an amount greater than zero that fits the currency.`,
  refund_cancel_tickets_unavailable: t`Cancelling tickets with a refund is turned off for this space. Untick it, or cancel the tickets from the event.`,
  refund_cancel_tickets_not_event: t`Only a refund on an event ticket can cancel tickets. Untick it and approve again.`,
});

export function caseErrorMessage(error: unknown) {
  if (error instanceof StructuredApiError && error.code && CASE_ERRORS()[error.code]) return CASE_ERRORS()[error.code];
  return error instanceof Error ? error.message : t`That did not work. Try again.`;
}

/** "2 days", "6 hours", "30 minutes": a whole unit wherever the figure allows one. */
export function formatDuration(minutes: number) {
  if (minutes >= 1440 && minutes % 1440 === 0) return plural(minutes / 1440, { one: "# day", other: "# days" });
  if (minutes >= 60 && minutes % 60 === 0) return plural(minutes / 60, { one: "# hour", other: "# hours" });
  return plural(minutes, { one: "# minute", other: "# minutes" });
}

/** How a policy window reads back to staff: "2 days before", or "until the start". */
export function formatWindow(minutes: number) {
  return minutes <= 0 ? t`until the start` : t`${formatDuration(minutes)} before`;
}

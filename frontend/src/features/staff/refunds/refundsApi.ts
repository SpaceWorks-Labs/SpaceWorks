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
  open: "To decide", approved: "Approved", approval_failed: "Provider refused",
  declined: "Declined", withdrawn: "Withdrawn", void: "Closed",
};

export const REASON_LABELS: Record<RefundCase["reason_code"] | "capture_flagged", string> = {
  event_cancelled: "Event cancelled by the space", registration_cancelled: "Registration cancelled",
  booking_cancelled: "Booking cancelled", staff_cancelled: "Cancelled by staff",
  membership_cancelled: "Membership term cancelled",
  member_request: "Member asked",
  fee_waived: "Loan fee waived",
  capture_flagged: "Unexpected online payment",
  order_unfulfilled: "Order could not be seated",
  ticket_type_changed: "Changed to a cheaper ticket",
  pass_occurrence_cancelled: "Pass occurrence cancelled",
  submission_disqualified: "Project disqualified",
  team_rejected: "Team rejected",
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

export type ApproveBody = { amount?: string; reason?: string; note?: string; receipt?: RefundReceipt; keep_membership?: boolean };

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

const CASE_ERRORS: Record<string, string> = {
  refund_case_closed: "Someone already decided this refund. The list has been refreshed.",
  refund_exceeds_balance: "That is more than is left to refund on this charge.",
  refund_rail_unavailable: "Online refunds are switched off on this deployment. Decline the case and return the money another way.",
  refund_receipt_required: "Record how the money was returned: method, reference and date.",
  refund_amount_invalid: "Enter an amount greater than zero that fits the currency.",
};

export function caseErrorMessage(error: unknown) {
  if (error instanceof StructuredApiError && error.code && CASE_ERRORS[error.code]) return CASE_ERRORS[error.code];
  return error instanceof Error ? error.message : "That did not work. Try again.";
}

/** "2 days", "6 hours", "30 minutes": a whole unit wherever the figure allows one. */
export function formatDuration(minutes: number) {
  const plural = (count: number, unit: string) => `${count} ${unit}${count === 1 ? "" : "s"}`;
  if (minutes >= 1440 && minutes % 1440 === 0) return plural(minutes / 1440, "day");
  if (minutes >= 60 && minutes % 60 === 0) return plural(minutes / 60, "hour");
  return plural(minutes, "minute");
}

/** How a policy window reads back to staff: "2 days before", or "until the start". */
export function formatWindow(minutes: number) {
  return minutes <= 0 ? "until the start" : `${formatDuration(minutes)} before`;
}

import type { QueryClient } from "@tanstack/react-query";

import type {
  LoanAccountabilityChargeResult, LoanAccountabilityRow, LoanCharge, LoanCharges, LoanFeeWaiver, LoanFeeWaiverResult,
} from "../../../generated/api";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import { invalidatePaymentViews } from "../paymentsApi";

export type { LoanAccountabilityChargeResult, LoanAccountabilityRow, LoanCharge, LoanCharges, LoanFeeWaiver, LoanFeeWaiverResult };

export type WaiverComponent = "rental" | "late" | "damage" | "lost";

/** The four loan fees a waiver can cover. The refundable deposit is never one of them. */
export const WAIVER_COMPONENTS: ReadonlyArray<readonly [WaiverComponent, string, string]> = [
  ["rental", "Rental", "loan_rental"],
  ["late", "Late fee", "loan_late_fee"],
  ["damage", "Damage", "loan_damage"],
  ["lost", "Lost item", "loan_lost"],
];

export const COMPONENT_LABELS: Record<string, string> = Object.fromEntries(
  WAIVER_COMPONENTS.map(([key, label]) => [key, label]),
);

const STATUS: Record<string, [string, "success" | "warn" | "neutral" | "info"]> = {
  pending: ["Pending", "warn"],
  paid_online: ["Paid online", "success"],
  paid_offline: ["Paid in person", "success"],
  waived: ["Waived", "info"],
  canceled: ["Canceled", "neutral"],
};

export function chargeStatus(status: string) {
  return STATUS[status] ?? [status, "neutral" as const];
}

/** Only these loan states can carry charges: a pending or rejected request owes nothing. */
const CHARGEABLE = new Set(["accepted", "issued", "partially_returned", "returned", "closed_with_issue"]);
export function loanCanCarryCharges(status: string) {
  return CHARGEABLE.has(status);
}

export function loanChargesKey(makerspaceId: number, requestId: number) {
  return ["loan-charges", makerspaceId, requestId] as const;
}

const base = (makerspaceId: number, requestId: number) => `/admin/makerspace/${makerspaceId}/requests/${requestId}`;

export function getLoanCharges(makerspaceId: number, requestId: number) {
  return staffRequest<LoanCharges>(`${base(makerspaceId, requestId)}/charges`);
}

export function waiveLoanFees(makerspaceId: number, requestId: number, components: WaiverComponent[], reason: string) {
  return staffRequest<LoanFeeWaiverResult>(`${base(makerspaceId, requestId)}/fee-waivers`, {
    method: "POST", body: JSON.stringify({ components, reason }),
  });
}

export function revokeLoanWaiver(makerspaceId: number, requestId: number, waiverId: number, reason: string) {
  return staffRequest<LoanFeeWaiver>(`${base(makerspaceId, requestId)}/fee-waivers/${waiverId}/revoke`, {
    method: "POST", body: JSON.stringify({ reason }),
  });
}

export function chargeAccountability(makerspaceId: number, requestId: number, rowId: number, amount: string, note: string) {
  return staffRequest<LoanAccountabilityChargeResult>(`${base(makerspaceId, requestId)}/accountability/${rowId}/charge`, {
    method: "POST", body: JSON.stringify(note ? { amount, note } : { amount }),
  });
}

/** A charge decision changes this loan's panel, the payment ledger and (for a waiver) the refund queue. */
export function invalidateLoanCharges(queryClient: QueryClient, makerspaceId: number, requestId: number) {
  queryClient.invalidateQueries({ queryKey: loanChargesKey(makerspaceId, requestId) });
  queryClient.invalidateQueries({ queryKey: ["refund-cases", makerspaceId] });
  invalidatePaymentViews(queryClient, makerspaceId);
}

/** The panel stays quiet when the viewer may not read this loan's money, or the switch is off. */
export function isHiddenError(error: unknown) {
  return error instanceof StructuredApiError && (error.status === 403 || error.status === 404);
}

const ERRORS: Record<string, string> = {
  waiver_reason_required: "Give a reason. It is kept with the waiver for the audit trail.",
  waiver_exists: "One of these fees is already waived on this loan. Leave it out, or revoke that waiver first.",
  charge_exists: "This item already has a charge. The panel has been refreshed.",
  return_photo_required: "This item has no return photo, so only No charge can be saved.",
};

export function chargeErrorMessage(error: unknown) {
  if (error instanceof StructuredApiError) {
    if (error.code && ERRORS[error.code]) return ERRORS[error.code];
    if (error.status === 404) return "This is switched off for the space, or you cannot change this loan's charges.";
  }
  return error instanceof Error ? error.message : "That did not work. Try again.";
}

/** "Suggested from the price list": where the prefilled damage/lost amount came from. */
export function suggestionHint(source: string) {
  if (source === "unit_cost") return "Suggested from the item's unit cost.";
  if (source === "none") return "No suggestion is set for this item. Enter the amount.";
  return "Suggested from the price list.";
}

/** Rows a return recorded that still need a decision: no charge raised and "No charge" not decided. */
export function undecidedRows(data: LoanCharges | undefined) {
  return data?.pricing_enabled ? data.accountability.filter(row => !row.charge && !row.no_charge_decided) : [];
}

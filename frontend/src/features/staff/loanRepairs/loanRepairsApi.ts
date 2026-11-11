import { StructuredApiError, staffRequest } from "../../../lib/api";

// Hand-written until `frontend/src/generated/api.ts` is regenerated from the OpenAPI schema
// (`LoanRepairs`, `LoanRepairLine`, `LoanRepairIssue`, `LoanRepairHandoffResult`).
export type LoanRepairPart = { id: number; kind: string; name: string; quantity: number; to_buy_item_id: number | null };
export type LoanRepairToBuy = {
  id: number; name: string; quantity: number; status: string;
  estimated_unit_cost: string | null; actual_unit_cost: string | null; receipts: { id: number }[];
};
export type LoanRepairIssue = {
  id: number; state: string; title: string; quote_state: string; quote_amount: string | null; quote_currency: string;
  payout_amount: string | null; payout_currency: string;
  work_order: { id: number; status: string } | null; parts: LoanRepairPart[]; to_buy_items: LoanRepairToBuy[];
};
export type LoanRepairLine = {
  accountability_id: number; product_name: string; quantity: number; asset_tag: string; remark: string;
  evidence_id: number | null;
  /** A repair is open for this line. A reviewer (accept_request) sees this but no repair detail (221c). */
  handed_off?: boolean;
  issue: LoanRepairIssue | null;
};
export type LoanRepairs = { request_id: number; lines: LoanRepairLine[] };
export type LoanRepairHandoffResult = { created: boolean; issue_id: number; line: LoanRepairLine };

/** Only a return can leave a damaged line behind. */
const RETURNED = new Set(["partially_returned", "returned", "closed_with_issue"]);
export function loanCanHaveRepairs(status: string) {
  return RETURNED.has(status);
}

export function loanRepairsKey(makerspaceId: number, requestId: number) {
  return ["loan-repairs", makerspaceId, requestId] as const;
}

const path = (makerspaceId: number, requestId: number) => `/admin/makerspaces/${makerspaceId}/requests/${requestId}/repairs`;

export function getLoanRepairs(makerspaceId: number, requestId: number) {
  return staffRequest<LoanRepairs>(path(makerspaceId, requestId));
}

/** `note` (optional, up to 2000 characters) is recorded on the repair's triage step for the item managers. */
export function handOffToRepairs(makerspaceId: number, requestId: number, accountabilityId: number, note = "") {
  return staffRequest<LoanRepairHandoffResult>(path(makerspaceId, requestId), {
    method: "POST", body: JSON.stringify({ accountability_id: accountabilityId, ...(note.trim() ? { note: note.trim() } : {}) }),
  });
}

/** Repairs switched off (404) or not this viewer's area (403): the panel stays out of the way. */
export function isHiddenError(error: unknown) {
  return error instanceof StructuredApiError && (error.status === 403 || error.status === 404);
}

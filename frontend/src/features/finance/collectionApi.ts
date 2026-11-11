import { t } from "@lingui/core/macro";

import { StructuredApiError, staffRequest } from "../../lib/api";

/** Parity O-B3 routes (`payments/views_collection_sheet.py`); local until the generated client catches up. */
export type CollectionRowInput = { payment_id: number; method: string; reference: string; received_at?: string };
export type CollectionOutcome = "recorded" | "awaiting_confirmation" | "failed";
export type CollectionResult = { index: number; payment_id: number; outcome: CollectionOutcome; code: string; detail: string };
export type CollectionSheetResponse = {
  summary: { rows: number; recorded: number; awaiting_confirmation: number; failed: number };
  results: CollectionResult[];
};
export type CashHandoverInput = { collector_id: number; amount: string; currency: string; entry_date?: string; note?: string };
export type CashHandoverResult = { entry_id: number; collector_id: number; amount: string; currency: string };

/** The server's sheet ceiling (`collection_sheet.MAX_ROWS`). */
export const MAX_SHEET_ROWS = 200;

const space = (id: number) => `/admin/makerspace/${id}/billing`;

export const collectionApi = {
  recordSheet: (id: number, rows: CollectionRowInput[]) =>
    staffRequest<CollectionSheetResponse>(`${space(id)}/collection-sheet`, { method: "POST", body: JSON.stringify({ rows }) }),
  handover: (id: number, input: CashHandoverInput) =>
    staffRequest<CashHandoverResult>(`${space(id)}/cash-handovers`, { method: "POST", body: JSON.stringify(input) }),
};

/** Plain words for a failed row's typed code; the server's own detail is the fallback. */
export function rowFailureText(code: string, detail: string): string {
  switch (code) {
    case "payment_terminal": return t`Already paid, waived or closed.`;
    case "duplicate_in_sheet": return t`This charge is on the sheet twice; only the first row counts.`;
    case "not_found": return t`No charge with this number in this space.`;
    case "self_confirmation": return t`You can't confirm a payment you recorded yourself.`;
    case "permission_denied": return t`You can't record this charge.`;
    default: return detail || t`This row could not be recorded.`;
  }
}

/** A whole-sheet refusal (quota, switch off, access) in words. */
export function sheetErrorText(error: unknown): string {
  if (error instanceof StructuredApiError) {
    if (error.code === "collection_sheet_rows_monthly_quota_reached") {
      return t`This sheet would go over the space's monthly allowance for collection-sheet rows. Record fewer rows, or record the rest one at a time from Payments.`;
    }
    if (error.status === 403) return t`You don't have access to record payments in this space.`;
    if (error.status === 404) return t`The collection sheet is not switched on for this space.`;
    return error.detail || error.message;
  }
  return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
}

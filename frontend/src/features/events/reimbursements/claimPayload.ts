import { t } from "@lingui/core/macro";
import type { ClaimLine } from "./types";

export function claimDraftLines(lines: ClaimLine[]) {
  if (!lines.length || lines.length > 50 || new Set(lines.map(line => line.line_uuid)).size !== lines.length) throw new Error(t`Add between one and fifty distinct expenses.`);
  return lines.map(line => {
    if (!Number.isSafeInteger(line.original_amount_minor) || line.original_amount_minor < 1 || line.original_amount_minor > 9000000000000000) throw new Error(t`Enter a positive whole amount in original minor units for every expense.`);
    if (!/^[A-Z]{3}$/.test(line.original_currency) || !/^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?$/.test(line.fx_rate) || Number(line.fx_rate) <= 0) throw new Error(t`Check each original currency and positive exchange rate.`);
    if (!line.vendor.trim() || !line.traveller.trim() || !line.description.trim() || !line.expense_date || !line.rate_date) throw new Error(t`Complete the vendor, traveller, description and dates for each expense.`);
    if (!line.receipt || !Number.isSafeInteger(line.receipt.receipt_total_minor) || line.receipt.receipt_total_minor < line.original_amount_minor
      || !Number.isSafeInteger(line.receipt.asset_id) || line.receipt.asset_id < 1 || !Number.isSafeInteger(line.receipt.generation) || line.receipt.generation < 1 || !/^[a-f0-9]{64}$/.test(line.receipt.sha256)) throw new Error(t`Attach a ready receipt and check that its full total covers the amount claimed.`);
    const { lodging_starts_on, lodging_ends_on, lodging_nights, ...base } = line;
    if (line.category === "lodging") {
      if (!lodging_starts_on || !lodging_ends_on || lodging_ends_on <= lodging_starts_on || !Number.isSafeInteger(lodging_nights) || lodging_nights! < 1 || lodging_nights! > 365) throw new Error(t`Check the lodging dates and number of nights.`);
      return { ...base, lodging_starts_on, lodging_ends_on, lodging_nights };
    }
    return base;
  });
}

import { t } from "@lingui/core/macro";

import { SETTLEMENT_METHODS, settlementMethodLabel } from "../staff/paymentsApi";
import type { CollectionResult, CollectionRowInput } from "./collectionApi";

/** One editable line of the collection sheet. `result` is the server's answer from the last submit. */
export type SheetRow = { key: number; payment: string; method: string; reference: string; date: string; result?: CollectionResult };
export type SheetDefaults = { method: string; date: string };

const CODES: readonly string[] = SETTLEMENT_METHODS.map(([code]) => code);
// Words people type in a spreadsheet's "method" column, mapped onto the receipt's method codes.
const ALIASES: Record<string, string> = {
  cash: "cash", upi: "upi", gpay: "upi", phonepe: "upi", paytm: "upi", bank: "bank_transfer", banktransfer: "bank_transfer",
  neft: "bank_transfer", imps: "bank_transfer", rtgs: "bank_transfer", transfer: "bank_transfer", card: "card_machine",
  cardmachine: "card_machine", pos: "card_machine", cheque: "cheque", check: "cheque", other: "other",
};

export function localToday(now = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function methodCode(text: string, fallback: string): string {
  const raw = text.trim();
  if (!raw) return fallback;
  const squashed = raw.toLowerCase().replace(/[^a-z]/g, "");
  return ALIASES[squashed] ?? CODES.find((code) => settlementMethodLabel(code).toLowerCase() === raw.toLowerCase()) ?? raw;
}

/** ISO dates pass through; day-first dates (10/11/2026, 10-11-2026, 10.11.2026) become ISO; anything else is kept to be flagged. */
function isoDate(text: string, fallback: string): string {
  const raw = text.trim();
  if (!raw) return fallback;
  const dayFirst = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(raw);
  return dayFirst ? `${dayFirst[3]}-${dayFirst[2].padStart(2, "0")}-${dayFirst[1].padStart(2, "0")}` : raw;
}

/**
 * Rows pasted from a spreadsheet: charge number, method, reference, received date — tab-separated (what a
 * spreadsheet copies) or comma-separated. A first line that does not start with a number is a header and is skipped.
 */
export function parsePasted(text: string, defaults: SheetDefaults, nextKey: () => number): SheetRow[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  return lines.flatMap((line, index) => {
    const cells = (line.includes("\t") ? line.split("\t") : line.split(",")).map((cell) => cell.trim().replace(/^"|"$/g, ""));
    if (index === 0 && !/^#?\d+$/.test(cells[0] ?? "")) return [];
    return [{ key: nextKey(), payment: (cells[0] ?? "").replace(/^#/, ""), method: methodCode(cells[1] ?? "", defaults.method),
      reference: cells[2] ?? "", date: isoDate(cells[3] ?? "", defaults.date) }];
  });
}

/** What is wrong with a row before it is sent, or null. Duplicates are flagged on the later copy, as the server does. */
export function rowProblem(row: SheetRow, earlier: SheetRow[], today: string): string | null {
  const payment = row.payment.trim();
  if (!/^\d+$/.test(payment) || Number(payment) < 1) return t`Enter the charge number from the payments list.`;
  if (earlier.some((other) => other.payment.trim() === payment)) return t`This charge is already on the sheet.`;
  if (!CODES.includes(row.method)) return t`Pick how the money was paid.`;
  if (row.reference.length > 64) return t`Keep the reference to 64 characters.`;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(row.date) || Number.isNaN(new Date(`${row.date}T00:00:00`).getTime())) {
    return t`Use a date like ${today}.`;
  }
  if (row.date > today) return t`The money can't be received in the future.`;
  return null;
}

export function sheetProblems(rows: SheetRow[], today: string): (string | null)[] {
  return rows.map((row, index) => rowProblem(row, rows.slice(0, index), today));
}

/** The request body: a past date is recorded at local noon; today's date at the moment of recording. */
export function toInput(row: SheetRow, today: string, now = new Date()): CollectionRowInput {
  const received = row.date === today ? now : new Date(`${row.date}T12:00:00`);
  return { payment_id: Number(row.payment.trim()), method: row.method, reference: row.reference.trim(), received_at: received.toISOString() };
}

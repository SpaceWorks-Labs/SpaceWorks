import type { PricingDefault, PricingDefaultWrite } from "./pricingApi";

/** The editable copy of a rate card: every number is the string the input holds. */
export type LineDraft = { component: string; amount: string; cap: string; grace_units: string;
  billing_increment: string; minimum: string };
export type LendingDraft = { deposit_mode: "none" | "fixed" | "per_product"; deposit_amount: string;
  deposit_blocks_issue: boolean; late_per_day: string; late_cap: string; grace_days: string };
export type PricingDraft = { mode: "free" | "paid"; lines: LineDraft[]; lending: LendingDraft | null };
export type DraftProblems = Record<string, string>;

const MONEY = /^\d{1,10}(\.\d{1,3})?$/;
const WHOLE = /^\d+$/;

export function toDraft(card: PricingDefault): PricingDraft {
  return {
    mode: card.mode,
    lines: card.lines.map(line => ({
      component: line.component, amount: line.amount, cap: line.cap ?? "",
      grace_units: String(line.grace_units ?? 0), billing_increment: String(line.billing_increment ?? 0),
      minimum: String(line.minimum ?? 0),
    })),
    lending: card.lending ? {
      deposit_mode: card.lending.deposit_mode ?? "none", deposit_amount: card.lending.deposit_amount ?? "0.00",
      deposit_blocks_issue: Boolean(card.lending.deposit_blocks_issue), late_per_day: card.lending.late_per_day ?? "0.00",
      late_cap: card.lending.late_cap ?? "0.00", grace_days: String(card.lending.grace_days ?? 0),
    } : null,
  };
}

function whole(value: string, max: number) {
  return WHOLE.test(value.trim()) && Number(value) <= max;
}

/** Field problems keyed `line.<component>.<field>` or `lending.<field>`; empty means valid. */
export function validateDraft(card: PricingDefault, draft: PricingDraft): DraftProblems {
  const problems: DraftProblems = {};
  const money = "Enter an amount of 0 or more, with no more decimals than the currency has.";
  for (const line of draft.lines) {
    const spec = card.lines.find(row => row.component === line.component);
    if (!spec || spec.read_only) continue;
    const key = `line.${line.component}`;
    if (!MONEY.test(line.amount.trim())) problems[`${key}.amount`] = money;
    if (spec.has_cap && line.cap.trim() && !MONEY.test(line.cap.trim())) problems[`${key}.cap`] = `${money} Leave empty for no cap.`;
    if (spec.has_grace && !whole(line.grace_units, 365)) problems[`${key}.grace_units`] = "Enter whole days from 0 to 365.";
    if (spec.has_increment && !whole(line.billing_increment, 1440)) problems[`${key}.billing_increment`] = "Enter whole minutes from 0 to 1440.";
    if (spec.has_minimum && !whole(line.minimum, 1440)) problems[`${key}.minimum`] = "Enter whole minutes from 0 to 1440.";
  }
  if (draft.lending) {
    for (const field of ["deposit_amount", "late_per_day", "late_cap"] as const) {
      if (!MONEY.test(draft.lending[field].trim())) problems[`lending.${field}`] = money;
    }
    if (!whole(draft.lending.grace_days, 365)) problems["lending.grace_days"] = "Enter whole days from 0 to 365.";
  }
  return problems;
}

/** The PUT / impact body: only the fields each line takes, and never a read-only line. */
export function toWrite(card: PricingDefault, draft: PricingDraft): PricingDefaultWrite {
  const lines = draft.lines.flatMap(line => {
    const spec = card.lines.find(row => row.component === line.component);
    if (!spec || spec.read_only) return [];
    return [{
      component: line.component, amount: line.amount.trim(),
      ...(spec.has_cap ? { cap: line.cap.trim() || null } : {}),
      ...(spec.has_grace ? { grace_units: Number(line.grace_units) } : {}),
      ...(spec.has_increment ? { billing_increment: Number(line.billing_increment) } : {}),
      ...(spec.has_minimum ? { minimum: Number(line.minimum) } : {}),
    }];
  });
  const lending = draft.lending ? {
    deposit_mode: draft.lending.deposit_mode, deposit_amount: draft.lending.deposit_amount.trim(),
    deposit_blocks_issue: draft.lending.deposit_blocks_issue, late_per_day: draft.lending.late_per_day.trim(),
    late_cap: draft.lending.late_cap.trim(), grace_days: Number(draft.lending.grace_days),
  } : undefined;
  // The rate-line type carries read-only display fields; the server ignores them on write.
  return { mode: draft.mode, lines: lines as PricingDefaultWrite["lines"], ...(lending ? { lending } : {}) };
}

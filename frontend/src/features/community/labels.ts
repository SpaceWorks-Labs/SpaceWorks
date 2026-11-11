import { t } from "@lingui/core/macro";
import { formatMoney } from "../../lib/money";
import type { VolunteerCredit } from "./api";

export const entryStatusLabel = (status: string) => ({
  pending: t`Waiting for approval`, approved: t`Approved`, rejected: t`Rejected`,
} as Record<string, string>)[status] ?? status;

export const creditStatusLabel = (status: string) => ({
  available: t`Available`, used: t`Applied to a charge`, void: t`Voided`,
} as Record<string, string>)[status] ?? status;

export function hoursLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60), rest = minutes % 60;
  if (!hours) return t`${rest} min`;
  return rest ? t`${hours} h ${rest} min` : t`${hours} h`;
}

/** What one credit is worth: an amount off, or free days on the next term. */
export const creditLabel = (credit: Pick<VolunteerCredit, "kind" | "amount" | "days" | "currency">) =>
  credit.kind === "free_days" ? t`${credit.days} free days` : t`${formatMoney(credit.amount, credit.currency)} off`;

import { currencyExponent, formatMinorMoney } from "../../../lib/money";
import type { LineDraft, PricingDraft } from "./pricingDraft";

/**
 * Exact minor units from a decimal string in the currency's own exponent (cents for EUR, yen for JPY,
 * fils for KWD); null when it is not a valid amount, or has more decimals than the currency has.
 * Called without a currency it keeps the two-decimal behaviour.
 */
export function toCents(value: string | null | undefined, currency = "USD"): number | null {
  const places = currencyExponent(currency);
  const text = (value ?? "").trim();
  if (!/^\d+(\.\d+)?$/.test(text)) return null;
  const [whole, fraction = ""] = text.split(".");
  if (fraction.length > places) return null;
  return Number(whole) * 10 ** places + (places ? Number(fraction.padEnd(places, "0")) : 0);
}

/**
 * The step a charge moves in, in minor units. Stripe and Razorpay need the last digit of a
 * three-decimal currency (KWD, BHD, ...) to be 0, so the server rounds those to 10 fils, once.
 */
export function chargeStep(currency: string): number {
  return currencyExponent(currency) === 3 ? 10 : 1;
}

/**
 * One quote line as the server builds it (`pricing/quote.py` `line`): unit x quantity, the
 * cap applied to that raw amount first, then rounded HALF-UP to cents. The quantity is the
 * fraction `numerator / denominator` so hours (minutes / 60) stay exact.
 */
export function lineCents(unit: number, numerator: number, denominator = 1, cap: number | null = null, step = 1) {
  if (cap !== null && unit * numerator > cap * denominator) return cap;
  return Math.floor((2 * unit * numerator + denominator * step) / (2 * denominator * step)) * step;
}

/** Billed minutes: rounded up to the increment, never below the minimum (a 0-minute job bills none). */
export function billedMinutes(minutes: number, increment: number, minimum = 0) {
  if (minutes <= 0) return 0;
  const step = increment > 1 ? increment : 1;
  return Math.max(Math.ceil(minutes / step) * step, minimum);
}

const money = (minor: number, currency: string) => formatMinorMoney(minor, currency);
const find = (draft: PricingDraft, key: string): LineDraft | undefined => draft.lines.find(line => line.component === key);
const whole = (value?: string) => (/^\d+$/.test(value ?? "") ? Number(value) : 0);

export type WorkedExample = { lead: string; notes: string[] };

/** The live example under the rates, from the unsaved form values. */
export function workedExample(domain: string, draft: PricingDraft, currency: string): WorkedExample | null {
  const free = draft.mode === "free";
  const amount = (line?: LineDraft) => toCents(line?.amount, currency) ?? 0;
  const cap = (line?: LineDraft) => (line?.cap.trim() ? toCents(line.cap, currency) : null);
  const step = chargeStep(currency);
  if (domain === "loans") {
    const notes: string[] = [];
    const lending = draft.lending;
    if (!free && lending?.deposit_mode === "fixed" && (toCents(lending.deposit_amount, currency) ?? 0) > 0) {
      notes.push(`Plus a refundable deposit of ${money(toCents(lending.deposit_amount, currency) ?? 0, currency)} per loan.`);
    } else if (!free && lending?.deposit_mode === "per_product") notes.push("Plus each item's own refundable deposit.");
    const late = toCents(lending?.late_per_day, currency) ?? 0;
    if (!free && late > 0) {
      const lateCap = toCents(lending?.late_cap, currency) ?? 0;
      notes.push(`Each day late after ${whole(lending?.grace_days)} grace days adds ${money(late, currency)}`
        + `${lateCap > 0 ? `, up to ${money(lateCap, currency)}` : ""}.`);
    }
    if (free) return { lead: "Loans are free: a 3-day loan of 1 item costs nothing.", notes };
    const perDay = find(draft, "rental_per_day");
    const total = amount(find(draft, "rental_per_loan")) + lineCents(amount(perDay), 3, 1, cap(perDay), step);
    return { lead: `A 3-day loan of 1 item costs ${money(total, currency)} in rental.`, notes };
  }
  if (domain === "machines") {
    if (free) return { lead: "Machines are free: a 90-minute job costs nothing.", notes: [] };
    const time = find(draft, "time");
    const billed = billedMinutes(90, whole(time?.billing_increment), whole(time?.minimum));
    const material = amount(find(draft, "material"));
    const total = lineCents(amount(time), billed, 60, null, step) + lineCents(material, 10, 1, null, step) + amount(find(draft, "per_job"));
    const notes = billed !== 90 && amount(time) > 0 ? [`Machine time is billed as ${billed} minutes.`] : [];
    return { lead: `A 90-minute job${material > 0 ? " using 10 units of material" : ""} costs ${money(total, currency)}.`, notes };
  }
  if (domain === "bookings") {
    if (free) return { lead: "Bookings are free: a 2-hour booking costs nothing.", notes: [] };
    const hourly = find(draft, "per_hour");
    const billed = billedMinutes(120, whole(hourly?.billing_increment));
    const total = amount(find(draft, "per_booking")) + lineCents(amount(hourly), billed, 60, cap(hourly), step);
    return { lead: `A 2-hour booking costs ${money(total, currency)}.`, notes: [] };
  }
  if (domain === "events") {
    const price = amount(find(draft, "per_registration"));
    return { lead: free || price <= 0 ? "New events start free." : `New events start at ${money(price, currency)} per registration.`,
      notes: ["Published events keep their own price."] };
  }
  return null;
}

import { t } from "@lingui/core/macro";

import { formatLocale } from "./format";

/**
 * The one money formatter. Every screen shows a server-computed amount through here: the locale's
 * currency format ("€12.50", "₹1,200.00"), falling back to "12.50 EUR" for a code Intl does not know.
 * The browser never re-prices; this only formats what the server sent.
 */
export function formatMoney(amount: string | number | null | undefined, currency: string): string {
  const value = Number(amount ?? 0);
  const code = (currency || "").toUpperCase();
  try {
    // The server's exponent, not Intl's: an IDR major amount keeps its cents (CLDR would round them away).
    const exponent = currencyExponent(code);
    return new Intl.NumberFormat(formatLocale(), { style: "currency", currency: code,
      minimumFractionDigits: exponent, maximumFractionDigits: exponent }).format(value);
  } catch {
    return `${Number.isFinite(value) ? value.toFixed(2) : String(amount)} ${code}`.trim();
  }
}

/** A price label: "Free" for exactly nothing owed, otherwise `formatMoney` (a discount line stays negative). */
export function formatPrice(amount: string | number | null | undefined, currency: string): string {
  return Number(amount ?? 0) === 0 ? t`Free` : formatMoney(amount, currency);
}

/**
 * An integer amount in the currency's minor units (cents, paise; yen has none). The exponent is the
 * server's (`currencyExponent`), and the digits are placed exactly (BigInt), so a large ledger figure never rounds.
 */
export function formatMinorMoney(minor: number | null | undefined, currency: string): string {
  if (minor == null || !Number.isSafeInteger(minor)) return t`Unavailable`;
  const code = (currency || "").toUpperCase();
  const exponent = currencyExponent(code);
  let format: Intl.NumberFormat;
  try {
    format = new Intl.NumberFormat(formatLocale(), { style: "currency", currency: code,
      minimumFractionDigits: exponent, maximumFractionDigits: exponent });
  } catch {
    return `${minorToDecimal(minor, code)} ${code}`.trim();
  }
  if (exponent === 0) return format.format(minor);
  const value = BigInt(minor), factor = 10n ** BigInt(exponent);
  const whole = value / factor, remainder = value < 0n ? -(value % factor) : value % factor;
  return format.formatToParts(whole === 0n && value < 0n ? -0 : Number(whole)).map((part) =>
    part.type === "fraction" ? remainder.toString().padStart(exponent, "0") : part.value).join("");
}

// The server's ISO 4217 table (backend/apps/payments/money.py), NOT Intl: CLDR gives 0 digits for
// IDR, HUF, COP, ... where the ledger keeps 2, which made every typed amount 100x off.
const ZERO_DECIMAL = new Set(["BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"]);
const THREE_DECIMAL = new Set(["BHD", "JOD", "KWD", "OMR", "TND"]);

/** How many decimal places a currency's minor unit has on the server (2 for EUR, 0 for JPY, 3 for KWD; else 2). */
export function currencyExponent(currency: string): number {
  const code = (currency || "").toUpperCase();
  return ZERO_DECIMAL.has(code) ? 0 : THREE_DECIMAL.has(code) ? 3 : 2;
}

/** A computed amount as text: two places, three only when a fils is present (matches the server's trim). */
export function fixedMoney(value: number): string {
  const text = (Math.round(value * 1000) / 1000).toFixed(3);
  return text.endsWith("0") ? text.slice(0, -1) : text;
}

/** Minor units as the plain decimal a person types ("1250" EUR -> "12.50"); exact, no float rounding. */
export function minorToDecimal(minor: number | null | undefined, currency: string): string {
  if (minor == null || !Number.isSafeInteger(minor)) return "";
  const exponent = currencyExponent(currency);
  if (exponent === 0) return String(minor);
  const value = BigInt(minor), factor = 10n ** BigInt(exponent);
  const magnitude = value < 0n ? -value : value;
  return `${value < 0n ? "-" : ""}${magnitude / factor}.${(magnitude % factor).toString().padStart(exponent, "0")}`;
}

/**
 * A typed decimal amount ("12.5", "-3", "1200.00") as integer minor units, or null when it is not a
 * valid amount in that currency (more decimals than the currency has, or beyond a safe integer).
 */
export function decimalToMinor(text: string, currency: string): number | null {
  const match = /^(-)?(\d+)(?:\.(\d*))?$/.exec(text.trim());
  if (!match) return null;
  const exponent = currencyExponent(currency);
  const fraction = match[3] ?? "";
  if (fraction.length > exponent) return null;
  const minor = BigInt(match[2]) * 10n ** BigInt(exponent) + BigInt(fraction.padEnd(exponent, "0") || "0");
  const signed = match[1] ? -minor : minor;
  return signed >= BigInt(Number.MIN_SAFE_INTEGER) && signed <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(signed) : null;
}

/** Translated wording for a payment, settlement or payout method code (shared by finance, payouts and the ledger). */
export function paymentMethodLabel(method: string): string {
  switch (method) {
    case "cash": return t`Cash`;
    case "upi": return t`UPI`;
    case "bank_transfer": return t`Bank transfer`;
    case "card": return t`Card`;
    case "card_machine": return t`Card machine`;
    case "cheque": return t`Cheque`;
    case "online": return t`Online`;
    case "paypal": return t`PayPal`;
    case "wise": return t`Wise`;
    case "other": return t`Other`;
    default: return method.replace(/_/g, " ");
  }
}

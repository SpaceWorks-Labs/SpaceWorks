import { formatLocale } from "../../../lib/format";
export const reasonIsValid = (value: string) => /^[a-z][a-z0-9_]{0,63}$/.test(value);
export function money(minor: number | null | undefined, currency: string) {
  if (minor == null || !Number.isSafeInteger(minor)) return "Unavailable";
  try {
    const format = new Intl.NumberFormat(formatLocale(), { style: "currency", currency });
    const exponent = format.resolvedOptions().maximumFractionDigits ?? 2;
    const value = BigInt(minor), factor = 10n ** BigInt(exponent);
    const whole = value / factor, remainder = value < 0n ? -(value % factor) : value % factor;
    return format.formatToParts(whole === 0n && value < 0n ? -0 : whole).map(part =>
      part.type === "fraction" ? remainder.toString().padStart(exponent, "0") : part.value).join("");
  } catch { return `${currency} ${minor} minor units`; }
}
/** datetime-local is deliberately labelled UTC; never interpret it in the browser timezone. */
export function utcInstant(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?$/.test(value)) return null;
  const date = new Date(`${value}Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 16) === value.slice(0, 16)
    ? date.toISOString().replace(/\.000Z$/, "Z") : null;
}
export const scopeIdentity = (actorId: number, makerspaceId?: number) => `${window.location.host}:${actorId}:${makerspaceId ?? "member"}`;

// Central date, time, number, percent and currency formatting (phase 8 i18n).
//
// Every formatter reads the active app locale; none passes `undefined` to Intl. The
// formatting locale keeps the browser's regional variant when it is the same language
// (an en-GB browser in the English app still sees day-first dates), so routing formatting
// through here changes nothing for today's English-only deployments.
// Machine-readable values (CSV, API timestamps, ISO strings) never go through this module.
import { activeLocale } from "./i18n";

export function formatLocale(): string {
  const active = activeLocale();
  const preferred = typeof navigator === "undefined" ? [] : navigator.languages ?? [navigator.language];
  return preferred.find((tag) => tag && tag.toLowerCase().split("-")[0] === active.split("-")[0]) ?? active;
}

type DateInput = Date | string | number;
const asDate = (value: DateInput) => (value instanceof Date ? value : new Date(value));

export function formatDate(value: DateInput, options: Intl.DateTimeFormatOptions = { dateStyle: "medium" }): string {
  return asDate(value).toLocaleDateString(formatLocale(), options);
}

export function formatTime(value: DateInput, options: Intl.DateTimeFormatOptions = { timeStyle: "short" }): string {
  return asDate(value).toLocaleTimeString(formatLocale(), options);
}

export function formatDateTime(
  value: DateInput,
  options: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short" },
): string {
  return asDate(value).toLocaleString(formatLocale(), options);
}

export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(formatLocale(), options).format(value);
}

export function formatPercent(value: number, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(formatLocale(), { style: "percent", ...options }).format(value);
}

/** Today as YYYY-MM-DD on the clock of `timeZone` (the space's zone), not the browser's or UTC. */
export function localDateIn(timeZone?: string, now: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  } catch {
    return now.toISOString().slice(0, 10);
  }
}

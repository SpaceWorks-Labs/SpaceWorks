import { consoleSessionHref } from "../../lib/api/sessionContext";
import type { OverviewSpace } from "./platformOverviewApi";

const NUMBER = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

export function formatBytes(value: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value, unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${NUMBER.format(size)} ${units[unit]}`;
}

/** One figure in its unit. Null means "not measurable here" (a percent over all time). */
export function formatValue(unit: string, value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  if (unit === "bytes") return formatBytes(value);
  if (unit === "percent") return `${NUMBER.format(value)}%`;
  if (unit === "hours") return `${NUMBER.format(value)} h`;
  return NUMBER.format(value);
}

/** A decimal string in one currency. Never combined with another currency. */
export function formatMoney(currency: string, amount: string) {
  const value = Number(amount);
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currency.toUpperCase() }).format(value);
  } catch {
    return `${currency.toUpperCase()} ${amount}`;
  }
}

export const EXCLUDED_LABEL: Record<string, string> = {
  archived: "Archived", importing: "Importing", aborted: "Import aborted",
};

/** The console tab each block drills into; the overview links there with `?space=<id>`. */
export const DRILL_TAB: Record<string, string> = {
  people: "members", lending: "requests", machines: "machines", events: "events", bookings: "bookings",
  membership: "members", operations: "email-logs", money: "finance",
};

/** A space's console page, or null for a space the console cannot open (archived, importing). */
export function drillHref(space: OverviewSpace | undefined, tab: string) {
  if (!space || space.excluded_reason) return null;
  return consoleSessionHref(`/admin/${tab}?space=${space.id}`, "platform");
}

export function offText(offIn: number) {
  return offIn ? `Off in ${offIn} ${offIn === 1 ? "space" : "spaces"}` : "On in every space";
}

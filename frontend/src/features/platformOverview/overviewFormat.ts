import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import type { OverviewSpace } from "./platformOverviewApi";

const NUMBER = new Intl.NumberFormat(formatLocale(), { maximumFractionDigits: 1 });

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
    return new Intl.NumberFormat(formatLocale(), { style: "currency", currency: currency.toUpperCase() }).format(value);
  } catch {
    return `${currency.toUpperCase()} ${amount}`;
  }
}

export const EXCLUDED_LABEL: Record<string, string> = {
  archived: t`Archived`, importing: t`Importing`, aborted: t`Import aborted`,
};

/** A directory-hidden space is left out by default too, but it is live: the console still opens it. */
export function isLiveSpace(space: OverviewSpace) {
  return !space.excluded_reason || space.excluded_reason === "directory_hidden";
}

/** The console tab each block drills into; the overview links there with `?space=<id>`. */
export const DRILL_TAB: Record<string, string> = {
  people: "members", lending: "requests", machines: "machines", events: "events", bookings: "bookings",
  membership: "members", operations: "email-logs", money: "finance",
};

/** A space's console page, or null for a space the console cannot open (archived, importing).
 * `for_space` rather than `space`: some panels (bookings) read `space` as one of their own rows. */
export function drillHref(space: OverviewSpace | undefined, tab: string) {
  if (!space || !isLiveSpace(space)) return null;
  return consoleSessionHref(`/admin/${tab}?for_space=${space.id}`, "platform");
}

export function offText(offIn: number) {
  return offIn ? t`Off in ${offIn} ${offIn === 1 ? "space" : "spaces"}` : t`On in every space`;
}

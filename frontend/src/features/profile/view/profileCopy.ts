import { plural, t } from "@lingui/core/macro";
import { formatLocale } from "../../../lib/format";
import type { StatusPreset, VerifiedAchievement } from "../accountProfileTypes";

export const statusLabel = (preset: StatusPreset): string => ({
  student: t`Student`, working: t`Working`, freelancing: t`Freelancing`, looking_for_work: t`Looking for work`,
  open_to_collaborate: t`Open to collaborate`, building_startup: t`Building a startup`, other: t`Other`, "": "",
}[preset]);

export const STATUS_PRESETS: StatusPreset[] = ["student", "working", "freelancing", "looking_for_work", "open_to_collaborate", "building_startup", "other"];

/** Verified rows are structured; the UI writes the sentence (the server never sends prose). */
export function verifiedSentence(row: VerifiedAchievement): string {
  const event = row.event_title ?? "";
  switch (row.kind) {
    case "award":
      return row.prize_name ? t`Won ${row.prize_name} at ${event}` : row.rank ? t`Placed #${row.rank} at ${event}` : t`Won an award at ${event}`;
    case "peoples_choice": return t`People's choice at ${event}`;
    case "role": return row.role ? t`${row.role} at ${event}` : t`Took part in ${event}`;
    case "speaker": return t`Spoke at ${event}`;
    case "attended": { const count = row.count ?? 0; return plural(count, { one: "Attended # verified event", other: "Attended # verified events" }); }
  }
}

export function monthYear(value: string) {
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(formatLocale(), { month: "short", year: "numeric" });
}

export function eventDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString(formatLocale(), { day: "numeric", month: "short", year: "numeric" });
}

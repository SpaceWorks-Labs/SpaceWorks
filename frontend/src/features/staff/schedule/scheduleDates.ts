import { calendarDate, dayStart } from "../../discovery/calendarDates";

export type ScheduleView = "month" | "week" | "day" | "list";

/** Calendar dates are plain `YYYY-MM-DD` strings in the space's own time zone. */
export function todayIn(timeZone: string) {
  return calendarDate(new Date(), timeZone);
}

export function addDays(day: string, days: number) {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date + days)).toISOString().slice(0, 10);
}

export function addMonths(day: string, months: number) {
  const [year, month] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1 + months, 1)).toISOString().slice(0, 10);
}

/** Monday of the week holding `day`. */
export function weekStart(day: string) {
  const [year, month, date] = day.split("-").map(Number);
  const weekday = (new Date(Date.UTC(year, month - 1, date)).getUTCDay() + 6) % 7;
  return addDays(day, -weekday);
}

/** The inclusive window a view asks the server for (the server allows at most 62 days). */
export function viewWindow(view: ScheduleView, anchor: string): { start: string; end: string } {
  if (view === "day") return { start: anchor, end: anchor };
  if (view === "week") { const start = weekStart(anchor); return { start, end: addDays(start, 6) }; }
  if (view === "month") { const start = `${anchor.slice(0, 7)}-01`; return { start, end: addDays(addMonths(start, 1), -1) }; }
  return { start: anchor, end: addDays(anchor, 13) };
}

/** Where Previous/Next lands for each view. */
export function stepAnchor(view: ScheduleView, anchor: string, direction: 1 | -1) {
  if (view === "month") return addMonths(anchor, direction);
  return addDays(anchor, direction * (view === "day" ? 1 : view === "week" ? 7 : 14));
}

export function daysBetween(start: string, end: string) {
  const out: string[] = [];
  for (let day = start; day <= end && out.length < 63; day = addDays(day, 1)) out.push(day);
  return out;
}

/** True when the interval touches the local calendar day (a zero-length entry counts on its own day). */
export function onDay(entry: { starts_at: string; ends_at: string }, day: string, timeZone: string) {
  const [year, month, date] = day.split("-").map(Number);
  const low = dayStart(year, month, date, timeZone).getTime();
  const high = dayStart(year, month, date + 1, timeZone).getTime();
  const starts = Date.parse(entry.starts_at);
  const ends = Math.max(Date.parse(entry.ends_at), starts);
  return starts < high && (ends > low || (ends === starts && starts >= low));
}

import type { Interval, OpeningHours } from "../staff/makerspaceProfileForm";

export const WEEKDAYS = [
  ["mon", "Monday"], ["tue", "Tuesday"], ["wed", "Wednesday"], ["thu", "Thursday"],
  ["fri", "Friday"], ["sat", "Saturday"], ["sun", "Sunday"],
] as const;
type Weekday = (typeof WEEKDAYS)[number][0];

export type HoursSummary = {
  /** One line for today, in the makerspace's own time zone ("Open today 09:00–17:00", "Closed today"). */
  today: string;
  week: { day: string; hours: string; isToday: boolean }[];
};

function ranges(intervals: Interval[] | undefined) {
  return intervals?.length ? intervals.map((slot) => `${slot.start}–${slot.end}`).join(", ") : "Closed";
}

function zoned(now: Date, timeZone: string | undefined) {
  try {
    const weekday = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone }).format(now).toLowerCase().slice(0, 3);
    return { weekday: weekday as Weekday, date: new Intl.DateTimeFormat("en-CA", { timeZone }).format(now) };
  } catch {
    // An unknown zone string must not take the page down; fall back to the visitor's clock.
    return zoned(now, undefined);
  }
}

/** Null when the space has published no weekly hours, so the header can omit the row entirely. */
export function summariseHours(hours: OpeningHours | undefined, timeZone?: string, now = new Date()): HoursSummary | null {
  const weekly = (hours && "weekly" in hours ? hours.weekly : {}) as Partial<Record<Weekday, Interval[]>>;
  if (!Object.keys(weekly).length) return null;
  const exceptions = (hours && "exceptions" in hours ? hours.exceptions : {}) ?? {};
  const { weekday, date } = zoned(now, timeZone);
  const todays = exceptions[date] ?? weekly[weekday];
  return {
    today: todays?.length ? `Open today ${ranges(todays)}` : "Closed today",
    week: WEEKDAYS.map(([key, day]) => ({ day, hours: ranges(weekly[key]), isToday: key === weekday })),
  };
}

import { t } from "@lingui/core/macro";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { RouteLink } from "../../components/ui/RouteLink";
import { formatLocale } from "../../lib/format";
import { currentMonth } from "../discovery/calendarDates";
import { MonthCalendar, type CalendarEntry } from "../discovery/MonthCalendar";
import type { PublicEventDetail } from "../events/eventTicketTypes";
import { eventWhen, useFeaturedEvents } from "../public/FeaturedActivities";
import { MakerspaceSection } from "../public/MakerspaceSection";

const UPCOMING_LIMIT = 5;

/** `YYYY-MM` shifted by whole months (pure calendar arithmetic, no time zone involved). */
export function shiftMonth(month: string, delta: number): string {
  const [year, number] = month.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, number - 1 + delta, 1));
  return `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function isLive(event: Pick<PublicEventDetail, "starts_at" | "ends_at">, now: number) {
  return new Date(event.starts_at).getTime() <= now && now <= new Date(event.ends_at).getTime();
}

/**
 * The space's public events calendar (decision 307a): live-now card, a month grid, an agenda list
 * and the next few events. It reads the SAME public, listed events as the events page (one query
 * key), so nothing private can appear here that the events page does not already show.
 */
export function EventsCalendarSection({ slug, path, timeZone, enabled }: { slug: string; path: (sub?: string) => string; timeZone: string; enabled: boolean }) {
  const events = useFeaturedEvents(slug, enabled);
  const [month, setMonth] = useState(() => currentMonth(timeZone));
  const list = useMemo(() => events.data ?? [], [events.data]);
  const now = Date.now();
  const entries: CalendarEntry[] = useMemo(() => list.map((event) => ({
    id: event.public_token, startsAt: event.starts_at, endsAt: event.ends_at, label: event.title, href: path(`events/${event.public_token}`),
  })), [list, path]);
  // Ended events never open the section: a calendar of only the past is noise (the events page owns "All events").
  if (!enabled || !events.data || !list.some((event) => new Date(event.ends_at).getTime() >= now)) return null;
  const live = list.filter((event) => isLive(event, now));
  const upcoming = list.filter((event) => new Date(event.starts_at).getTime() > now).slice(0, UPCOMING_LIMIT);
  const label = new Date(`${month}-01T12:00:00Z`).toLocaleDateString(formatLocale(), { month: "long", year: "numeric", timeZone: "UTC" });
  const nav = "inline-flex h-11 w-11 items-center justify-center rounded-control border border-outline hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
  return <MakerspaceSection id="calendar" title={t`Events calendar`}>
    {live.length ? <ul aria-label={t`Happening now`} className="mb-4 grid gap-2">{live.map((event) =>
      <li key={event.public_token} className="rounded-xl border border-success bg-success-soft p-4">
        <p className="text-xs font-semibold uppercase text-success-ink">{t`Live now`}</p>
        <RouteLink href={path(`events/${event.public_token}`)} className="text-lg font-semibold text-ink underline">{event.title}</RouteLink>
        <p className="text-sm text-muted">{eventWhen(event, timeZone)}</p>
      </li>)}</ul> : null}
    <div className="mb-2 flex items-center justify-between gap-2">
      <button type="button" className={nav} aria-label={t`Previous month`} onClick={() => setMonth(shiftMonth(month, -1))}><ChevronLeft aria-hidden size={18} /></button>
      <p className="font-semibold" aria-live="polite">{label}</p>
      <button type="button" className={nav} aria-label={t`Next month`} onClick={() => setMonth(shiftMonth(month, 1))}><ChevronRight aria-hidden size={18} /></button>
    </div>
    <MonthCalendar month={month} entries={entries} label={t`Public events`} timeZone={timeZone} />
    {upcoming.length ? <>
      <h3 className="title-section mb-2">{t`Coming up`}</h3>
      <ul className="grid gap-2">{upcoming.map((event) => <li key={event.public_token} className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl border border-line bg-panel p-3">
        <RouteLink href={path(`events/${event.public_token}`)} className="font-semibold text-brand-ink underline">{event.title}</RouteLink>
        <span className="text-sm text-muted">{eventWhen(event, timeZone)}</span>
      </li>)}</ul>
    </> : null}
  </MakerspaceSection>;
}

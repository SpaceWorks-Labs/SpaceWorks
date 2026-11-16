import { t } from "@lingui/core/macro";
import { formatLocale } from "../../lib/format";
import type { DisplayCalendar, DisplayEvent, HereNow, MachinesNow } from "./api";
import { machineStatusLabel } from "./MachinesNowSection";
import { othersLabel, PersonCard } from "./PersonCard";

const MAX_TV_CARDS = 6;
const MAX_TV_EVENTS = 6;

const when = (event: DisplayEvent, timeZone: string) => new Intl.DateTimeFormat(formatLocale(), {
  weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone }).format(new Date(event.starts_at));

const heading = "mb-6 text-4xl font-semibold text-ink";

export function HereNowPanel({ data }: { data: HereNow }) {
  const shown = data.people.slice(0, MAX_TV_CARDS);
  const others = data.total - shown.length;
  return <section aria-labelledby="tv-here" className="grid gap-6">
    <h2 id="tv-here" className={heading}>{t`Here now`}</h2>
    {data.total === 0 ? <p className="text-3xl text-muted">{t`No one is checked in right now.`}</p> : <>
      {shown.length ? <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{shown.map((card) => <li key={`${card.handle ?? card.display_name}-${card.since}`}><PersonCard card={card} tv /></li>)}</ul> : null}
      {others > 0 ? <p className="text-3xl font-semibold text-ink">{othersLabel(others, shown.length > 0)}</p> : null}
    </>}
  </section>;
}

export function MachinesPanel({ data }: { data: MachinesNow }) {
  return <section aria-labelledby="tv-machines" className="grid gap-6">
    <h2 id="tv-machines" className={heading}>{t`Machines now`}</h2>
    <p className="text-3xl text-ink">{t`${data.free} free · ${data.in_use} in use · ${data.out_of_service} out of service`}</p>
    <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{data.items.map((item) =>
      <li key={`${item.name}-${item.type}`} className="flex items-center justify-between gap-4 rounded-xl border border-line bg-panel p-5">
        <span className="min-w-0"><span className="block break-words text-2xl font-semibold text-ink">{item.name}</span><span className="block text-lg text-muted">{item.type}</span></span>
        <span className={`rounded-full border px-3 py-1 text-lg font-semibold ${item.status === "free" ? "border-success text-success-ink" : item.status === "in_use" ? "border-warn text-warn-ink" : "border-line text-muted"}`}>{machineStatusLabel(item.status)}</span>
      </li>)}</ul>
  </section>;
}

/** Live-now card plus the next events: the calendar at room-reading distance. */
export function CalendarPanel({ data, timeZone, now }: { data: DisplayCalendar; timeZone: string; now: number }) {
  const upcoming = data.events.filter((event) => new Date(event.ends_at).getTime() >= now && !event.live).slice(0, MAX_TV_EVENTS);
  const month = new Date(`${data.month}-01T12:00:00Z`).toLocaleDateString(formatLocale(), { month: "long", year: "numeric", timeZone: "UTC" });
  return <section aria-labelledby="tv-calendar" className="grid gap-6">
    <h2 id="tv-calendar" className={heading}>{t`Events calendar`} <span className="text-2xl font-normal text-muted">{month}</span></h2>
    {data.live.map((event) => <div key={event.token} className="rounded-xl border border-success bg-success-soft p-6">
      <p className="text-lg font-semibold uppercase text-success-ink">{t`Live now`}</p>
      <p className="break-words text-4xl font-semibold text-ink">{event.title}</p>
      {event.location ? <p className="text-xl text-muted">{event.location}</p> : null}
    </div>)}
    {upcoming.length === 0 && data.live.length === 0 ? <p className="text-3xl text-muted">{t`No events coming up.`}</p> : null}
    <ul className="grid gap-3">{upcoming.map((event) => <li key={event.token} className="flex flex-wrap items-baseline justify-between gap-3 rounded-xl border border-line bg-panel p-5">
      <span className="break-words text-2xl font-semibold text-ink">{event.title}</span>
      <span className="text-xl text-muted">{when(event, timeZone)}</span>
    </li>)}</ul>
  </section>;
}

export function AnnouncementPanel({ text }: { text: string }) {
  return <section aria-labelledby="tv-note" className="grid gap-6">
    <h2 id="tv-note" className={heading}>{t`Announcement`}</h2>
    <p className="whitespace-pre-line break-words text-5xl leading-tight text-ink">{text}</p>
  </section>;
}

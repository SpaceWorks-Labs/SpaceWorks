import { t } from "@lingui/core/macro";
import { formatLocale } from "../../../lib/format";
import { RouteLink } from "../../../components/ui/RouteLink";
import { areaLabel, attentionHref, type AttentionRouting } from "../panels/dashboardAreas/attention";
import { layerLabel, statusLabel, type ScheduleEntry } from "./scheduleApi";
import { daysBetween, onDay, weekStart } from "./scheduleDates";
import { calendarDate } from "../../discovery/calendarDates";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
type Common = { entries: ScheduleEntry[]; timeZone: string; routing: AttentionRouting };

function dayTitle(day: string, style: "full" | "short") {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date)).toLocaleDateString(formatLocale(),
    style === "full" ? { dateStyle: "full", timeZone: "UTC" } : { weekday: "short", day: "numeric", timeZone: "UTC" });
}

function timeRange(entry: ScheduleEntry, timeZone: string) {
  const time = new Intl.DateTimeFormat(formatLocale(), { hour: "2-digit", minute: "2-digit", timeZone });
  return entry.starts_at === entry.ends_at ? time.format(new Date(entry.starts_at))
    : `${time.format(new Date(entry.starts_at))}–${time.format(new Date(entry.ends_at))}`;
}

/** One entry, linked to its own record when the viewer can open that page. */
export function EntryLink({ entry, timeZone, routing, compact = false }: { entry: ScheduleEntry; timeZone: string; routing: AttentionRouting; compact?: boolean }) {
  const href = attentionHref(entry.link, routing);
  const body = <>
    <span className="block font-semibold text-ink [overflow-wrap:anywhere]">{entry.title}</span>
    <span className="block text-xs text-muted">{timeRange(entry, timeZone)} · {layerLabel(entry.layer)}{compact ? "" : ` · ${statusLabel(entry.status)}`}</span>
  </>;
  const classes = `block rounded-lg border border-line bg-panel px-2 py-1.5 text-sm ${compact ? "" : "min-h-11 px-3 py-2"}`;
  return href ? <RouteLink href={href} className={`${classes} hover:bg-hover ${FOCUS}`}>{body}</RouteLink> : <div className={classes}>{body}</div>;
}

/** Month and week share one semantic table: rows of seven days, each cell listing that day's entries. */
export function CalendarGrid({ days, entries, timeZone, routing, label, month }: Common & { days: string[]; label: string; month?: string }) {
  const first = weekStart(days[0]);
  const cells = daysBetween(first, days[days.length - 1]);
  while (cells.length % 7) cells.push("");
  const weekday = new Intl.DateTimeFormat(formatLocale(), { weekday: "short", timeZone: "UTC" });
  return <div className="overflow-x-auto rounded-xl border border-line bg-panel" tabIndex={0} role="region" aria-label={label}>
    <table className="w-full min-w-[720px] table-fixed text-sm">
      <caption className="sr-only">{label}</caption>
      <thead><tr>{Array.from({ length: 7 }, (_, index) => <th scope="col" key={index} className="border border-line p-2 text-left">
        {weekday.format(new Date(Date.UTC(2026, 0, 5 + index)))}</th>)}</tr></thead>
      <tbody>{Array.from({ length: cells.length / 7 }, (_, row) => <tr key={row}>{cells.slice(row * 7, row * 7 + 7).map((day, index) => {
        const outside = !day || (month !== undefined && !day.startsWith(month));
        if (!day) return <td key={index} className="border border-line bg-surface" />;
        const items = entries.filter(entry => onDay(entry, day, timeZone));
        return <td key={day} className={`h-28 border border-line p-1.5 align-top ${outside ? "bg-surface" : ""}`}>
          <span className="block text-xs tabular-nums text-muted" aria-label={dayTitle(day, "full")}>{Number(day.slice(8))}</span>
          <ul className="mt-1 grid gap-1">{items.slice(0, 4).map(entry => <li key={`${entry.layer}:${entry.id}`}>
            <EntryLink entry={entry} timeZone={timeZone} routing={routing} compact /></li>)}</ul>
          {items.length > 4 ? <span className="mt-1 block text-xs text-muted">{t`+${items.length - 4} more`}</span> : null}
        </td>;
      })}</tr>)}</tbody>
    </table>
  </div>;
}

/** The day view and the phone list: entries under day headings, or under area headings for the Space Manager. */
export function AgendaList({ days, entries, timeZone, routing, groupBy }: Common & { days: string[]; groupBy: "day" | "area" }) {
  if (groupBy === "area") {
    const areas = [...new Set(entries.map(entry => entry.area))].sort();
    return <div className="grid gap-6">{areas.map(area => {
      const rows = entries.filter(entry => entry.area === area);
      return <section key={area} aria-labelledby={`schedule-area-${area}`} className="grid gap-2">
        <h2 id={`schedule-area-${area}`} className="title-section">{areaLabel(area)} <span className="font-normal text-muted">({rows.length})</span></h2>
        <ul className="grid gap-2">{rows.map(entry => <li key={`${entry.layer}:${entry.id}`}>
          <p className="mb-1 text-xs text-muted">{dayTitle(calendarDate(new Date(entry.starts_at), timeZone), "full")}</p>
          <EntryLink entry={entry} timeZone={timeZone} routing={routing} /></li>)}</ul>
      </section>;
    })}</div>;
  }
  return <div className="grid gap-5">{days.map(day => {
    const rows = entries.filter(entry => onDay(entry, day, timeZone));
    if (!rows.length) return null;
    return <section key={day} aria-label={dayTitle(day, "full")} className="grid gap-2">
      <h2 className="eyebrow">{dayTitle(day, "full")}</h2>
      <ul className="grid gap-2">{rows.map(entry => <li key={`${entry.layer}:${entry.id}`}><EntryLink entry={entry} timeZone={timeZone} routing={routing} /></li>)}</ul>
    </section>;
  })}</div>;
}

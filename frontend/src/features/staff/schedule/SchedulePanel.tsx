import { t } from "@lingui/core/macro";
import { useState } from "react";
import { formatLocale } from "../../../lib/format";
import { PageHeader, SegmentedControl } from "../../../components/ui";
import { QueryContent } from "../../../components/layouts/LayoutFrame";
import { useLayoutMedia } from "../../../components/layouts/useLayoutMedia";
import type { Makerspace } from "../panels/shared";
import { layerLabel, useSchedule, type ScheduleLayer } from "./scheduleApi";
import { daysBetween, stepAnchor, todayIn, viewWindow, type ScheduleView } from "./scheduleDates";
import { AgendaList, CalendarGrid } from "./ScheduleViews";

type Props = { makerspace: Makerspace; allowedTabs?: readonly string[]; guestOnly: boolean; singleTenantLocked: boolean;
  /** The Space Manager's list groups by area first (decision 242(k)). */ groupByArea: boolean };

/**
 * Decision 242(k): one staff Schedule. The server returns only the layers this person may see (bookings,
 * events, volunteer shifts, machine jobs, maintenance); the toggles hide layers on the client. Phones get
 * the list and day views, because a seven-column grid there is either squeezed or scrolled sideways.
 */
export function SchedulePanel({ makerspace, allowedTabs, guestOnly, singleTenantLocked, groupByArea }: Props) {
  const timeZone = makerspace.timezone || "UTC";
  const wide = useLayoutMedia("(min-width: 768px)");
  const [chosenView, setView] = useState<ScheduleView>("week");
  const view: ScheduleView = !wide && (chosenView === "month" || chosenView === "week") ? "list" : chosenView;
  const [anchor, setAnchor] = useState(() => todayIn(timeZone));
  const [hidden, setHidden] = useState<Set<ScheduleLayer>>(new Set());
  const [groupBy, setGroupBy] = useState<"day" | "area">(groupByArea ? "area" : "day");
  const { start, end } = viewWindow(view, anchor);
  const schedule = useSchedule(makerspace.id, start, end);
  const layers = schedule.data?.layers ?? [];
  const entries = (schedule.data?.entries ?? []).filter(entry => !hidden.has(entry.layer));
  const routing = { slug: makerspace.slug, guestOnly, singleTenantLocked, allowedTabs };
  const days = daysBetween(start, end);
  const toggle = (layer: ScheduleLayer) => setHidden(current => {
    const next = new Set(current);
    if (next.has(layer)) next.delete(layer); else next.add(layer);
    return next;
  });
  const views = [...(wide ? [{ value: "month", label: t`Month` }, { value: "week", label: t`Week` }] : []),
    { value: "day", label: t`Day` }, { value: "list", label: t`List` }];
  const range = rangeLabel(view, start, end);
  const common = { entries, timeZone, routing };
  return <div className="min-w-0">
    <PageHeader title={t`Schedule`} subtitle={t`What's booked, running and due across the areas you look after.`} meta={`${range} · ${timeZone}`} />
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <SegmentedControl label={t`Schedule view`} value={view} options={views} onChange={value => setView(value as ScheduleView)} />
      <div className="flex flex-wrap gap-2" role="group" aria-label={t`Move through dates`}>
        <button type="button" className="desk-button min-h-11" onClick={() => setAnchor(stepAnchor(view, anchor, -1))}>{t`Previous`}</button>
        <button type="button" className="desk-button min-h-11" onClick={() => setAnchor(todayIn(timeZone))}>{t`Today`}</button>
        <button type="button" className="desk-button min-h-11" onClick={() => setAnchor(stepAnchor(view, anchor, 1))}>{t`Next`}</button>
      </div>
      {view === "list" && groupByArea ? <SegmentedControl label={t`Group the list`} value={groupBy}
        options={[{ value: "area", label: t`By area` }, { value: "day", label: t`By day` }]} onChange={value => setGroupBy(value as "day" | "area")} /> : null}
    </div>
    {layers.length > 1 ? <fieldset className="mb-4 flex flex-wrap gap-x-4 gap-y-1">
      <legend className="mb-1 text-sm font-semibold">{t`Show`}</legend>
      {layers.map(layer => <label key={layer} className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4" checked={!hidden.has(layer)} onChange={() => toggle(layer)} />{layerLabel(layer)}
      </label>)}
    </fieldset> : null}
    <QueryContent state={schedule.isLoading ? { status: "loading" } : schedule.error
      ? { status: "error", error: t`Couldn't load the schedule. Try again.`, onRetry: () => { void schedule.refetch(); } } : { status: "ready" }}
      isEmpty={schedule.isSuccess && (!layers.length || !entries.length)}
      empty={{ message: !layers.length ? t`Nothing here is yours to schedule yet. Bookings, events, machine jobs and maintenance appear once you run one of those areas.`
        : t`Nothing scheduled for ${range}. Try another range or turn more layers on.` }}>
      {schedule.data && schedule.data.entries.length >= 500 ? <p role="status" className="mb-3 text-sm text-muted">{t`Showing the first 500 entries. Pick a shorter range to see everything.`}</p> : null}
      {view === "month" ? <CalendarGrid {...common} days={days} month={start.slice(0, 7)} label={t`Schedule for ${range}`} />
        : view === "week" ? <CalendarGrid {...common} days={days} label={t`Schedule for ${range}`} />
        : <AgendaList {...common} days={days} groupBy={view === "list" ? groupBy : "day"} />}
    </QueryContent>
  </div>;
}

function rangeLabel(view: ScheduleView, start: string, end: string) {
  const date = (day: string, options: Intl.DateTimeFormatOptions) => {
    const [year, month, value] = day.split("-").map(Number);
    return new Date(Date.UTC(year, month - 1, value)).toLocaleDateString(formatLocale(), { ...options, timeZone: "UTC" });
  };
  if (view === "month") return date(start, { month: "long", year: "numeric" });
  if (view === "day") return date(start, { dateStyle: "full" });
  return `${date(start, { day: "numeric", month: "short" })} – ${date(end, { day: "numeric", month: "short", year: "numeric" })}`;
}

import { useState } from "react";

import { ErrorText, ListRow, Skeleton, StatusBadge } from "../../components/ui";
import type { QueryState } from "../../components/ui";
import { ListLayout } from "../../components/layouts";
import { EventDrawer } from "./EventDrawer";
import { EventSeriesDrawer } from "./EventSeriesDrawer";
import type { StaffAuthUser } from "../../lib/api";
import { useAccessibleEvents } from "./eventStaffGrantsApi";
import { opsStatusLabel } from "./opsPresentation";
import { eventErrorText } from "./eventUi";
import type { GrantedListFrame } from "./GrantedResourcesPanel";

const permissionList = (permissions: string[] = []) => permissions.map((permission) => permission.replace(/_/g, " ")).join(", ");

export function GrantedEventsPanel({ makerspaceId, grants = [], frame }: { makerspaceId?: number; grants?: StaffAuthUser["event_grants"]; frame?: GrantedListFrame }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ id: number; makerspace_id: number } | null>(null);
  const [selectedSeries, setSelectedSeries] = useState<{ id: number; makerspace_id: number } | null>(null);
  const series = grants.filter((grant) => grant.event_id === null && grant.series_id !== null && (!makerspaceId || grant.makerspace_id === makerspaceId));
  const events = useAccessibleEvents(page, makerspaceId);
  // An opened assignment replaces the list with its own detail page, exactly like the Events console.
  if (selected) return <EventDrawer key={selected.id} eventId={selected.id} makerspaceId={selected.makerspace_id} onClose={() => setSelected(null)} />;
  if (selectedSeries) return <EventSeriesDrawer key={selectedSeries.id} seriesId={selectedSeries.id} makerspaceId={selectedSeries.makerspace_id} onClose={() => setSelectedSeries(null)}
    onSelectOccurrence={(id) => { setSelected({ id, makerspace_id: selectedSeries.makerspace_id }); setSelectedSeries(null); }} />;
  const retry = () => { void events.refetch(); };
  // Series grants come from the signed-in account, so they stay usable while the event page loads or fails.
  const state: QueryState = series.length ? { status: "ready" } : events.isLoading ? { status: "loading" }
    : events.error ? { status: "error", error: eventErrorText(events.error), onRetry: retry } : { status: "ready" };
  const rows = events.data?.results ?? [];
  return <ListLayout header={{ title: "Assigned events", subtitle: "Open an event to use your assigned permissions." }} {...frame}
    state={state} isEmpty={Boolean(events.data && !rows.length && !series.length)}
    empty={{ message: "No assigned events. Your staff access may have expired or been revoked." }}
    body={{ kind: "rows", rows: <>
      {series.length ? <section className="grid gap-3" aria-label="Assigned recurring series"><h2 className="title-section">Recurring series</h2>
        {series.map((grant) => <ListRow key={grant.series_id} title={grant.title} identity={{ kind: "icon", icon: "Calendar", tone: "accent" }}
          meta={permissionList(grant.permissions)} onClick={() => setSelectedSeries({ id: grant.series_id!, makerspace_id: grant.makerspace_id })} />)}
      </section> : null}
      {series.length && events.isLoading ? <div role="status" className="grid gap-3"><span className="sr-only">Loading assigned events…</span><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></div> : null}
      {series.length && events.error ? <ErrorText message={eventErrorText(events.error)} onRetry={retry} /> : null}
      {rows.length ? <section className="grid gap-3" aria-label="Assigned events list">{series.length ? <h2 className="title-section">Events</h2> : null}
        {rows.map((event) => <ListRow key={event.id} title={event.title} identity={{ kind: "date", date: event.starts_at }} draft={event.status === "draft"}
          onClick={() => setSelected(event)}
          meta={<>{new Date(event.starts_at).toLocaleString()}{event.location ? ` · ${event.location}` : ""}<span className="block">{permissionList(event.staff_permissions)}</span></>}
          right={<StatusBadge domain="event" status={event.status} label={opsStatusLabel(event.status)} />} />)}
      </section> : null}
    </> }}
    pagination={events.data?.count ? { page, pageSize: 24, count: events.data.count, onChange: setPage } : undefined} />;
}

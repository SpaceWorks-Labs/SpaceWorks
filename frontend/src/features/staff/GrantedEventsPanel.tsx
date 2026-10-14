import { useState } from "react";

import { EmptyState, Skeleton, StatusBadge } from "../../components/ui";
import { EventDrawer } from "./EventDrawer";
import { EventSeriesDrawer } from "./EventSeriesDrawer";
import type { StaffAuthUser } from "../../lib/api";
import { useAccessibleEvents } from "./eventStaffGrantsApi";
import { eventErrorText } from "./eventUi";
import { Panel } from "./panels/shared";

export function GrantedEventsPanel({ makerspaceId, grants = [] }: { makerspaceId?: number; grants?: StaffAuthUser["event_grants"] }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ id: number; makerspace_id: number } | null>(null);
  const [selectedSeries, setSelectedSeries] = useState<{ id: number; makerspace_id: number } | null>(null);
  const series = grants.filter((grant) => grant.event_id === null && grant.series_id !== null && (!makerspaceId || grant.makerspace_id === makerspaceId));
  const events = useAccessibleEvents(page, makerspaceId);
  return <Panel title="Assigned events">
    <p className="mb-4 text-sm text-muted">Open an event to use your assigned permissions.</p>
    {events.isLoading ? <Skeleton className="h-32 w-full" /> : null}
    {events.error ? <EmptyState title="Unable to load assigned events" description={eventErrorText(events.error)} action={<button className="desk-button" type="button" onClick={() => events.refetch()}>Retry</button>} /> : null}
    {events.data && !events.data.results.length && !series.length ? <EmptyState title="No assigned events" description="Your staff access may have expired or been revoked." /> : null}
    {series.length ? <section className="mb-4 grid gap-2" aria-label="Assigned recurring series"><h3 className="title-section">Recurring series</h3>{series.map((grant) => <button key={grant.series_id} className="desk-button-ghost h-auto justify-start border border-line p-4" type="button" onClick={() => setSelectedSeries({ id: grant.series_id!, makerspace_id: grant.makerspace_id })}><span className="text-left"><span className="font-semibold">{grant.title}</span><span className="mt-1 block text-xs text-muted">{grant.permissions.map((permission) => permission.replace(/_/g, " ")).join(", ")}</span></span></button>)}</section> : null}
    <div className="grid gap-2">{events.data?.results.map((event) => <button key={event.id} className="desk-button-ghost h-auto justify-between border border-line p-4" type="button" onClick={() => setSelected(event)}>
      <span className="text-left"><span className="font-semibold text-ink">{event.title}</span><span className="mt-1 block text-xs text-muted">{new Date(event.starts_at).toLocaleString()} · {event.location}</span><span className="mt-1 block text-xs text-muted">{event.staff_permissions?.map((permission) => permission.replace(/_/g, " ")).join(", ")}</span></span>
      <StatusBadge status={event.status} />
    </button>)}</div>
    {events.data ? <div className="mt-4 flex items-center justify-between gap-3 text-sm">
      <button className="desk-button" type="button" disabled={!events.data.previous} onClick={() => setPage(Math.max(1, page - 1))}>Previous</button>
      <span>Page {page}</span><button className="desk-button" type="button" disabled={!events.data.next} onClick={() => setPage(page + 1)}>Next</button>
    </div> : null}
    {selected ? <EventDrawer key={selected.id} eventId={selected.id} makerspaceId={selected.makerspace_id} onClose={() => setSelected(null)} /> : null}
    {selectedSeries ? <EventSeriesDrawer key={selectedSeries.id} seriesId={selectedSeries.id} makerspaceId={selectedSeries.makerspace_id} onClose={() => setSelectedSeries(null)} onSelectOccurrence={(id) => { setSelected({ id, makerspace_id: selectedSeries.makerspace_id }); setSelectedSeries(null); }} /> : null}
  </Panel>;
}

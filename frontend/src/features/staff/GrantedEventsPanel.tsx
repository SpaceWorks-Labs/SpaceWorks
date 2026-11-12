import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { eventPermissionLabel } from "./eventStaffPermissions";
import { useState } from "react";

import { ErrorText, ListRow, StatusBadge } from "../../components/ui";
import type { QueryState } from "../../components/ui";
import { ListLayout } from "../../components/layouts";
import { EventSeriesDrawer } from "./EventSeriesDrawer";
import type { StaffAuthUser } from "../../lib/api";
import { useAccessibleEvents } from "./eventStaffGrantsApi";
import { opsStatusLabel } from "./opsPresentation";
import { eventErrorText } from "./eventUi";
import type { GrantedListFrame } from "./GrantedResourcesPanel";
import { ScopedEventDrawer } from "./ScopedEventDrawer";
import { SpaceScope } from "./SpaceScope";
import { EventRegistrationQueue } from "./EventRegistrationQueue";
import { LogoLoader } from "../../components/LogoLoader";

const permissionList = (permissions: string[] = []) => permissions.map(eventPermissionLabel).join(", ");

export function GrantedEventsPanel({ makerspaceId, grants = [], frame }: { makerspaceId?: number; grants?: StaffAuthUser["event_grants"]; frame?: GrantedListFrame }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ id: number; makerspace_id: number } | null>(null);
  const [selectedSeries, setSelectedSeries] = useState<{ id: number; makerspace_id: number } | null>(null);
  const series = grants.filter((grant) => grant.event_id === null && grant.series_id !== null && (!makerspaceId || grant.makerspace_id === makerspaceId));
  const events = useAccessibleEvents(page, makerspaceId);
  const slugFor = (spaceId: number) => grants.find(grant => grant.makerspace_id === spaceId)?.makerspace_slug ?? "";
  // A22: grant holders who manage registrations get the cross-event queue for their space too.
  const [queueSpace, setQueueSpace] = useState<number | null>(null);
  const queueSpaces = [...new Set(grants.filter(grant => grant.permissions.includes("manage_registrations")
    && (!makerspaceId || grant.makerspace_id === makerspaceId)).map(grant => grant.makerspace_id))];
  // An opened assignment replaces the list with its own detail page, exactly like the Events console.
  if (selected) return <ScopedEventDrawer key={selected.id} eventId={selected.id} makerspaceId={selected.makerspace_id}
    slug={slugFor(selected.makerspace_id)} onClose={() => setSelected(null)} />;
  if (selectedSeries) return <SpaceScope makerspaceId={selectedSeries.makerspace_id} slug={slugFor(selectedSeries.makerspace_id)}>
    <EventSeriesDrawer key={selectedSeries.id} seriesId={selectedSeries.id} makerspaceId={selectedSeries.makerspace_id} onClose={() => setSelectedSeries(null)}
      onSelectOccurrence={(id) => { setSelected({ id, makerspace_id: selectedSeries.makerspace_id }); setSelectedSeries(null); }} /></SpaceScope>;
  if (queueSpace !== null) return <section className="grid gap-4">
    <button type="button" className="desk-button w-fit" onClick={() => setQueueSpace(null)}>{t`Back to assigned events`}</button>
    <EventRegistrationQueue makerspaceId={queueSpace} onOpenEvent={id => { setSelected({ id, makerspace_id: queueSpace }); setQueueSpace(null); }} />
  </section>;
  const retry = () => { void events.refetch(); };
  // Series grants come from the signed-in account, so they stay usable while the event page loads or fails.
  const state: QueryState = series.length ? { status: "ready" } : events.isLoading ? { status: "loading" }
    : events.error ? { status: "error", error: eventErrorText(events.error), onRetry: retry } : { status: "ready" };
  const rows = events.data?.results ?? [];
  return <ListLayout {...frame} header={{ ...(frame?.header ?? { title: t`Assigned events`, subtitle: t`Open an event to use your assigned permissions.` }),
    overflow: queueSpaces.map(spaceId => ({ label: queueSpaces.length > 1 ? t`Registrations waiting (${slugFor(spaceId)})` : t`Registrations waiting`,
      onClick: () => setQueueSpace(spaceId) })) }}
    state={state} isEmpty={Boolean(events.data && !rows.length && !series.length)}
    empty={{ message: t`No assigned events. Your staff access may have expired or been revoked.` }}
    body={{ kind: "rows", rows: <>
      {series.length ? <section className="grid gap-3" aria-label={t`Assigned recurring series`}><h2 className="title-section">{t`Recurring series`}</h2>
        {series.map((grant) => <ListRow key={grant.series_id} title={grant.title} identity={{ kind: "icon", icon: "Calendar", tone: "accent" }}
          meta={permissionList(grant.permissions)} onClick={() => setSelectedSeries({ id: grant.series_id!, makerspace_id: grant.makerspace_id })} />)}
      </section> : null}
      {series.length && events.isLoading ? <div role="status" className="grid gap-3"><span className="sr-only">{t`Loading assigned events…`}</span><LogoLoader size={48} className="min-h-20 py-3" /><LogoLoader size={48} className="min-h-20 py-3" /></div> : null}
      {series.length && events.error ? <ErrorText message={eventErrorText(events.error)} onRetry={retry} /> : null}
      {rows.length ? <section className="grid gap-3" aria-label={t`Assigned events list`}>{series.length ? <h2 className="title-section">{t`Events`}</h2> : null}
        {rows.map((event) => <ListRow key={event.id} title={event.title} identity={{ kind: "date", date: event.starts_at }} draft={event.status === "draft"}
          onClick={() => setSelected(event)}
          meta={<>{new Date(event.starts_at).toLocaleString(formatLocale())}{event.location ? ` · ${event.location}` : ""}<span className="block">{permissionList(event.staff_permissions)}</span>{event.registration_counts ? <span className="block tabular-nums">{t`${event.registration_counts.pending_approval} pending · ${event.registration_counts.waitlisted} waitlisted`}</span> : null}</>}
          right={<StatusBadge domain="event" status={event.status} label={opsStatusLabel(event.status)} />} />)}
      </section> : null}
    </> }}
    pagination={events.data?.count ? { page, pageSize: 24, count: events.data.count, onChange: setPage } : undefined} />;
}

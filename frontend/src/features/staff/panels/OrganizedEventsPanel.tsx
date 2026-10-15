import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import { ListRow, StatusBadge } from "../../../components/ui";
import { EventDrawer } from "../EventsPanel";
import { useEveryOrganizedEvent, useOrganizedEvents, type EventAdmin } from "../organizedEventsApi";
import { opsQueryState, useOpsTabs, opsStatusLabel } from "../opsPresentation";

const PAGE_SIZE = 50;
type SelectedEvent = Pick<EventAdmin, "id" | "makerspace_id">;

export function OrganizedEventsPanel() {
  const [selected, setSelected] = useState<SelectedEvent | null>(null);
  const tabs = useOpsTabs("organizedView", [{ key: "all", label: "All events" }, { key: "upcoming", label: "Upcoming" }, { key: "past", label: "Past" }], "all");
  const [pageState, setPageState] = useState({ page: 1, tab: tabs.active });
  // A page number belongs to the tab it was chosen on; switching tabs starts again at page 1.
  const page = pageState.tab === tabs.active ? pageState.page : 1;
  const setPage = (next: number) => setPageState({ page: next, tab: tabs.active });
  const dated = tabs.active !== "all";
  const paged = useOrganizedEvents(page, PAGE_SIZE);
  const every = useEveryOrganizedEvent(dated);
  const events = dated ? every : paged;
  // Upcoming and Past are filtered across every page, then paged here, so no event hides on another page.
  const now = new Date();
  const matching = dated ? (every.data?.results ?? []).filter(row => (new Date(row.ends_at) < now) === (tabs.active === "past")) : [];
  if (tabs.active === "past") matching.reverse();
  const count = dated ? matching.length : paged.data?.count ?? 0;
  const rows = dated ? matching.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : paged.data?.results ?? [];
  if (selected) return <EventDrawer key={selected.id} eventId={selected.id} makerspaceId={selected.makerspace_id} onClose={() => setSelected(null)} />;
  return <div onClickCapture={tabs.onClickCapture}><ListLayout header={{ title: "Organized events", subtitle: "Events you run with your organization, across spaces." }}
    state={opsQueryState(events, "organized events")} tabs={tabs.tabs} activeTab={tabs.active} isEmpty={events.isSuccess && !count}
    empty={{ message: dated ? `No ${tabs.active} organized events.` : "No organized events. Events your organization runs will appear here." }}
    body={{ kind: "rows", rows: rows.map(row => <ListRow key={row.id} title={row.title} identity={{ kind: "date", date: row.starts_at }} draft={row.status === "draft"}
      onClick={() => setSelected({ id: row.id, makerspace_id: row.makerspace_id })}
      meta={<><span>{new Date(row.starts_at).toLocaleString()} · {new Date(row.ends_at).toLocaleString()} · {row.location || "Location to be confirmed"}</span><span className="block">{row.organizers.map(organizer => <span className="block" key={organizer.slug}><span>{organizer.name}</span> <span>({organizer.slug})</span></span>)}</span></>}
      right={<div className="grid justify-items-end gap-2"><StatusBadge domain="event" status={row.status} label={opsStatusLabel(row.status)} /><RegistrationTotals event={row} />{row.capacity ? <progress className="h-1 w-28 accent-accent" value={row.registration_counts.registered + row.registration_counts.attended} max={row.capacity} aria-label={`${row.title} places filled`} /> : null}</div>} />) }}
    pagination={events.data ? { page, pageSize: PAGE_SIZE, count, onChange: setPage } : undefined} /></div>;
}

function RegistrationTotals({ event }: { event: EventAdmin }) {
  const counts = event.registration_counts;
  const pending = counts.pending_approval ?? 0;
  const rejected = counts.rejected ?? 0;
  const total = counts.registered + counts.attended + counts.waitlisted + counts.cancelled + pending + rejected;
  return <div className="text-right text-xs tabular-nums text-muted">
    <span className="block text-sm text-ink">{counts.registered + counts.attended} / {event.capacity || "unlimited"} going</span>
    <span className="block">{total} total</span><span className="block">{counts.registered} registered · {counts.attended} attended</span>
    <span className="block">{counts.waitlisted} waitlisted · {counts.cancelled} cancelled</span><span className="block">{pending} pending · {rejected} rejected</span>
  </div>;
}

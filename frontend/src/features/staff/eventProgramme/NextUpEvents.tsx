import { RouteLink } from "../../../components/ui/RouteLink";
export type NextUpEvent = { id: number; title: string; starts_at: string; ends_at: string; href: string };
/** Staff home passes its already permission-filtered events; no second event workflow or count fetch. */
export function NextUpEvents({ events, now = new Date() }: { events: NextUpEvent[]; now?: Date }) {
  const rows = events.filter(event => new Date(event.ends_at).getTime() >= now.getTime()).sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()).slice(0, 3);
  return <section aria-label="Next up" className="grid gap-3"><h2 className="title-section">Next up</h2>{rows.length ? <ul className="grid gap-3">{rows.map(event => <li key={event.id} className="flex min-h-11 flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-panel p-4"><div className="grid gap-1"><h3 className="font-semibold">{event.title}</h3><p className="text-sm text-muted">{new Date(event.starts_at).getTime() <= now.getTime() ? "Happening now" : new Date(event.starts_at).toLocaleString()}</p></div><RouteLink href={event.href} className="desk-button">Open event</RouteLink></li>)}</ul> : <p className="rounded-2xl border border-dashed border-line p-4 text-sm text-muted">No upcoming events for your access.</p>}</section>;
}

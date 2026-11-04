import { RouteLink } from "../../components/ui/RouteLink";

// Release 2 (#128 C-36): the crew card the server projects for an event page's crew section.
export type CrewCard = { handle: string; display_name: string; crew_role: string };

/** Approved crew who opted in and keep a public profile: name (to their profile), and crew role. */
export function PublicCrewCards({ rows }: { rows: CrewCard[] }) {
  return <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Event crew">{rows.map(row =>
    <li key={row.handle} className="grid content-start gap-1 rounded-xl border border-line bg-panel p-4">
      <RouteLink className="inline-flex min-h-11 items-center font-semibold text-brand-ink underline"
        href={`/${encodeURIComponent(row.handle)}`}>{row.display_name || `@${row.handle}`}</RouteLink>
      {row.crew_role ? <p className="text-sm text-muted">{row.crew_role}</p> : null}
    </li>)}</ul>;
}

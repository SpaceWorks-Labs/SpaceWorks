import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PublicLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";
import { EmptyState, ErrorText, ListRow, Skeleton, StatusPill } from "../../components/ui";
import { publicV1Request } from "../../lib/api";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { DiscoveryEventImage } from "./DiscoveryEventImage";

type Results = import("../../generated/api").Discovery;
const field = "grid min-w-0 flex-1 basis-40 gap-1 text-sm font-semibold sm:flex-none";

export function EventDiscoverPage() {
  const [filters, setFilters] = useState({ q: "", date_from: "", date_to: "" });
  const [draft, setDraft] = useState(filters);
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["event-discover", filters, page], staleTime: 0,
    queryFn: () => publicV1Request<Results>(`/discover/events/?${new URLSearchParams(Object.fromEntries(Object.entries({ ...filters, page: String(page) }).filter(([, value]) => value)))}`),
  });
  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }}
    nav={[{ label: "Home", href: "/" }, { label: "Discover resources", href: "/discover/bookings" }]}
    headerAction={{ label: "Sign in", href: "/member" }} liveStatus={<ThemeToggle />}
    header={{ eyebrow: "Directory", title: "Discover events", subtitle: "Public events from makerspaces on this deployment that opted into its directory." }}
    // The filters stay on screen through loading and errors, so a bad date range can be corrected in place.
    state={{ status: "ready" }}
    footer={{ credit: "Powered by Space Works", links: [{ label: "About", href: "/about" }, { label: "License", href: LICENSE_URL, external: true }, { label: "Staff sign-in", href: "/admin" }] }}>
    <div className="grid gap-5">
      <form aria-label="Find events" className="desk-panel flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); setPage(1); setFilters(draft); }}>
        <label className={`${field} basis-full sm:basis-64 sm:flex-1`}>Search<input className="desk-input w-full" maxLength={200} value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} /></label>
        <label className={field}>From<input className="desk-input w-full" type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} /></label>
        <label className={field}>Through<input className="desk-input w-full" type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} /></label>
        <button className="desk-button-primary w-full sm:w-auto">Find events</button>
      </form>
      {query.isLoading ? <div role="status" aria-label="Loading events" className="grid gap-3"><span className="sr-only">Loading events…</span>{[0, 1, 2].map(item => <Skeleton key={item} className="h-20" />)}</div> : null}
      {query.error ? <ErrorText message="Unable to discover events. Check your dates and try again." onRetry={() => { void query.refetch(); }} /> : null}
      {!query.error && query.data ? <section aria-labelledby="discover-events-results" className="grid gap-3">
        <h2 id="discover-events-results" className="title-panel">{query.data.count} events</h2>
        {query.data.results.map((row) => <ListRow key={row.url} href={row.url} title={row.title}
          identity={row.image_url ? undefined : { kind: "date", date: row.date }}
          identityContent={row.image_url ? <DiscoveryEventImage url={row.image_url} alt={row.image_alt || row.title} /> : undefined}
          meta={<><span>{[row.makerspace_name, new Date(row.date).toLocaleString(), row.location].filter(Boolean).join(" · ")}</span>
            {row.description ? <span className="mt-1 block line-clamp-2">{row.description}</span> : null}</>}
          right={<div className="flex flex-wrap items-center gap-2">
            {row.audience_label ? <StatusPill label={row.audience_label} tone="info" /> : null}
            <StatusPill label={row.availability} tone={row.availability === "Full" ? "warn" : "success"} />
            {row.registration_count != null ? <span className="text-sm tabular-nums text-muted">{row.registration_count} registered</span> : null}
          </div>} />)}
        {!query.data.results.length ? <EmptyState message="No matching events." /> : null}
        <nav aria-label="Discovery pages" className="flex flex-wrap items-center justify-end gap-2 text-sm text-muted">
          <button type="button" className="desk-button" disabled={!query.data.previous} onClick={() => setPage(page - 1)}>Previous</button>
          <span>Page {page}</span>
          <button type="button" className="desk-button" disabled={!query.data.next} onClick={() => setPage(page + 1)}>Next</button>
        </nav>
      </section> : null}
    </div>
  </PublicLayout>;
}

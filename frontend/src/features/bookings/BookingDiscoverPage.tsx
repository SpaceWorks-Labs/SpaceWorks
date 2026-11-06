import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PublicLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";
import { EmptyState, ErrorText, ListRow, Skeleton } from "../../components/ui";
import { publicV1Request } from "../../lib/api";
import { LICENSE_URL } from "../inventory/PublicPageChrome";

type Results = { count: number; next: string | null; previous: string | null; results: {
  title: string; description: string; url: string; location: string; makerspace_name: string;
}[] };
const field = "grid min-w-0 flex-1 basis-40 gap-1 text-sm font-semibold sm:flex-none";

/** The deployment's resource directory: the sibling of Discover events, on the same public layout. */
export function BookingDiscoverPage() {
  const [draft, setDraft] = useState({ q: "", kind: "", location: "" });
  const [filters, setFilters] = useState(draft);
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["booking-discover", filters, page], staleTime: 0,
    queryFn: () => publicV1Request<Results>(`/discover/bookings/?${new URLSearchParams(Object.fromEntries(Object.entries({ ...filters, page: String(page) }).filter(([, value]) => value)))}`),
  });
  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }}
    nav={[{ label: t`Home`, href: "/" }, { label: t`Discover events`, href: "/discover" }]}
    headerAction={{ label: t`Sign in`, href: "/member" }} liveStatus={<ThemeToggle />}
    header={{ eyebrow: t`Directory`, title: t`Discover resources`, subtitle: t`Rooms and benches from makerspaces on this deployment that opted into its directory.` }}
    // The filters stay on screen through loading and errors, so a search can be corrected in place.
    state={{ status: "ready" }}
    footer={{ credit: "Powered by Space Works", links: [{ label: t`About`, href: "/about" }, { label: t`License`, href: LICENSE_URL, external: true }, { label: t`Staff sign-in`, href: "/admin" }] }}>
    <div className="grid gap-5">
      <form aria-label={t`Find resources`} className="desk-panel flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); setFilters(draft); setPage(1); }}>
        <label className={`${field} basis-full sm:basis-64 sm:flex-1`}>{t`Search resources`}<input className="desk-input w-full" maxLength={200} value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} /></label>
        <label className={field}>{t`Kind`}<select className="desk-input w-full" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}><option value="">{t`All resources`}</option><option value="dev_room">{t`Development room`}</option><option value="meeting">{t`Meeting room`}</option><option value="bench">{t`Bench`}</option><option value="other">{t`Other`}</option><option value="machine">{t`Machine time`}</option></select></label>
        <label className={field}>{t`Location`}<input className="desk-input w-full" maxLength={255} value={draft.location} onChange={(e) => setDraft({ ...draft, location: e.target.value })} /></label>
        <button type="submit" className="desk-button-primary w-full sm:w-auto">{t`Search`}</button>
      </form>
      {query.isLoading ? <div role="status" aria-label={t`Loading resources`} className="grid gap-3"><span className="sr-only">{t`Loading resources…`}</span>{[0, 1, 2].map(item => <Skeleton key={item} className="h-20" />)}</div> : null}
      {query.error ? <ErrorText message={t`Unable to discover resources.`} onRetry={() => { void query.refetch(); }} /> : null}
      {!query.error && query.data ? <section aria-labelledby="discover-resources-results" className="grid gap-3">
        <h2 id="discover-resources-results" className="title-panel">{query.data.count} resources</h2>
        {query.data.results.map((row) => <ListRow key={row.url} href={row.url} title={row.title}
          identity={{ kind: "icon", icon: "Calendar", tone: "info" }}
          meta={<><span>{[row.makerspace_name, row.location].filter(Boolean).join(" · ")}</span>
            {row.description ? <span className="mt-1 block line-clamp-2">{row.description}</span> : null}</>} />)}
        {!query.data.count ? <EmptyState message={t`No matching resources.`} /> : null}
        <nav aria-label={t`Resource discovery pages`} className="flex flex-wrap items-center justify-end gap-2 text-sm text-muted">
          <button type="button" className="desk-button" disabled={!query.data.previous} onClick={() => setPage(page - 1)}>{t`Previous`}</button>
          <span>{t`Page ${page}`}</span>
          <button type="button" className="desk-button" disabled={!query.data.next} onClick={() => setPage(page + 1)}>{t`Next`}</button>
        </nav>
      </section> : null}
    </div>
  </PublicLayout>;
}

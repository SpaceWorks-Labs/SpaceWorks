import { formatDateTime } from "../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { X } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PublicLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";
import { EmptyState, ErrorText, ListRow, StatusPill, PagePager } from "../../components/ui";
import { publicV1Request } from "../../lib/api";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { DiscoveryEventImage } from "./DiscoveryEventImage";
import { LogoLoader } from "../../components/LogoLoader";
import { SearchField } from "../../components/ui/SearchField";

type Results = import("../../generated/api").Discovery;
const field = "grid min-w-0 flex-1 basis-40 gap-1 text-sm font-semibold sm:flex-none";

type Organizer = { slug: string; name: string };
type OrganizerPage = { next: string | null; results: Organizer[] };

/** Public organisers of the events Discover lists now (slug and name only), every page of them. */
async function loadOrganizers() {
  const rows: Organizer[] = [];
  for (let page = 1; page <= 20; page += 1) {
    const data = await publicV1Request<OrganizerPage>(`/discover/events/organizers/?page=${page}`);
    rows.push(...data.results);
    if (!data.next) break;
  }
  return rows;
}

/** The list, plus a slug that arrived in a link but no longer organises anything listed (so the chip still reads true). */
export const organizerOptions = (rows: Organizer[], current: string) =>
  current && !rows.some(row => row.slug === current) ? [...rows, { slug: current, name: current }] : rows;

type Filters = { q: string; date_from: string; date_to: string; tag: string; organization: string };
/** Parity E-F3 (A14): `?tag=` and `?organization=<slug>` arrive from links on event and organisation pages. */
function initialFilters(): Filters {
  const params = new URLSearchParams(window.location.search);
  return { q: params.get("q") ?? "", date_from: params.get("date_from") ?? "", date_to: params.get("date_to") ?? "",
    tag: params.get("tag") ?? "", organization: params.get("organization") ?? "" };
}

export function EventDiscoverPage() {
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [draft, setDraft] = useState(filters);
  const organizers = useQuery({ queryKey: ["event-discover-organizers"], staleTime: 300_000, queryFn: loadOrganizers });
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["event-discover", filters, page], staleTime: 0,
    queryFn: () => publicV1Request<Results>(`/discover/events/?${new URLSearchParams(Object.fromEntries(Object.entries({ ...filters, page: String(page) }).filter(([, value]) => value)))}`),
  });
  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }}
    nav={[{ label: t`Home`, href: "/" }, { label: t`Discover resources`, href: "/discover/bookings" }]}
    headerAction={{ label: t`Sign in`, href: "/member" }} liveStatus={<ThemeToggle />}
    header={{ eyebrow: t`Directory`, title: t`Discover events`, subtitle: t`Public events from makerspaces on this deployment that opted into its directory.` }}
    // The filters stay on screen through loading and errors, so a bad date range can be corrected in place.
    state={{ status: "ready" }}
    footer={{ credit: "Powered by Space Works", links: [{ label: t`About`, href: "/about" }, { label: t`License`, href: LICENSE_URL, external: true }, { label: t`Privacy`, href: "/privacy" }, { label: t`Terms`, href: "/terms" }, { label: t`Staff sign-in`, href: "/admin" }] }}>
    <div className="grid gap-5">
      <form aria-label={t`Find events`} className="desk-panel flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); setPage(1); setFilters(draft); }}>
        <label className={`${field} basis-full sm:basis-64 sm:flex-1`}>{t`Search`}<SearchField className="desk-input w-full" maxLength={200} value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} /></label>
        <label className={field}>{t`From`}<input className="desk-input w-full" type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} /></label>
        <label className={field}>{t`Through`}<input className="desk-input w-full" type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} /></label>
        <label className={field}>{t`Tag`}<input className="desk-input w-full" maxLength={50} value={draft.tag} onChange={(e) => setDraft({ ...draft, tag: e.target.value })} /></label>
        <label className={field}>{t`Organiser`}<select className="desk-input w-full" value={draft.organization} onChange={(e) => setDraft({ ...draft, organization: e.target.value })}>
          <option value="">{t`Any organiser`}</option>
          {organizerOptions(organizers.data ?? [], draft.organization).map(row => <option key={row.slug} value={row.slug}>{row.name}</option>)}
        </select></label>
        <button className="desk-button-primary w-full sm:w-auto">{t`Find events`}</button>
      </form>
      <DiscoverChips filters={filters} organizers={organizers.data ?? []} onRemove={key => { const next = { ...filters, [key]: "" }; setPage(1); setFilters(next); setDraft(next); }} />
      {query.isLoading ? <LogoLoader label={t`Loading events`} size={48} className="min-h-20 py-3" /> : null}
      {query.error ? <ErrorText message={t`Unable to discover events. Check your dates and try again.`} onRetry={() => { void query.refetch(); }} /> : null}
      {!query.error && query.data ? <section aria-labelledby="discover-events-results" className="grid gap-3">
        <h2 id="discover-events-results" className="title-panel">{plural(query.data.count, { one: "# event", other: "# events" })}</h2>
        {query.data.results.map((row) => <ListRow key={row.url} href={row.url} title={row.title}
          identity={row.image_url ? undefined : { kind: "date", date: row.date }}
          identityContent={row.image_url ? <DiscoveryEventImage url={row.image_url} alt={row.image_alt || row.title} /> : undefined}
          meta={<><span>{[row.makerspace_name, formatDateTime(row.date), row.location].filter(Boolean).join(" · ")}</span>
            {row.description ? <span className="mt-1 block line-clamp-2">{row.description}</span> : null}</>}
          right={<div className="flex flex-wrap items-center gap-2">
            {row.audience_label ? <StatusPill label={row.audience_label} tone="info" /> : null}
            <StatusPill label={row.availability} tone={row.availability === "Full" ? "warn" : "success"} />
            {row.registration_count != null ? <span className="text-sm tabular-nums text-muted">{t`${row.registration_count} registered`}</span> : null}
          </div>} />)}
        {!query.data.results.length ? <EmptyState message={t`No events match. Try another search or date, or check back soon.`} /> : null}
        <PagePager page={page} setPage={setPage} next={query.data.next} />
      </section> : null}
    </div>
  </PublicLayout>;
}

/** The active tag and organiser filters as removable chips, so a link-applied filter is visible and easy to drop. */
function DiscoverChips({ filters, organizers, onRemove }: { filters: Filters; organizers: Organizer[]; onRemove: (key: "tag" | "organization") => void }) {
  const organiser = organizers.find(row => row.slug === filters.organization)?.name ?? filters.organization;
  const chips = ([["tag", t`Tag: ${filters.tag}`], ["organization", t`Organiser: ${organiser}`]] as const).filter(([key]) => filters[key]);
  if (!chips.length) return null;
  return <ul className="flex flex-wrap gap-2" aria-label={t`Active filters`}>{chips.map(([key, label]) => <li key={key}>
    <button type="button" className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line bg-panel px-4 text-sm font-semibold text-ink hover:border-brand-boundary"
      onClick={() => onRemove(key)}>{label}<X size={16} aria-hidden="true" /><span className="sr-only">{t`Remove filter`}</span></button>
  </li>)}</ul>;
}

import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { PublicWebsiteImage } from "../../components/PublicWebsiteImage";
import { PageMetadata } from "../../components/PageMetadata";
import { SkipLink } from "../../components/SkipLink";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { WebsiteProgramme, WebsiteSectionCard, type WebsiteLinks } from "./PublicEventWebsite";
import type { EventWebsite } from "./websiteTypes";

/** Read the current gated projection rather than retaining a detached speaker/session snapshot. */
export function PublicWebsiteDetailPage({ view }: { view: "schedule" | "session" | "speaker" }) {
  const { slug, publicToken = "", sessionSlug, speakerSlug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const path = useTenantPath(makerspaceSlug);
  const location = useLocation();
  const allowed = tenant.mode !== "single" || !slug || slug === tenant.slug;
  const query = useQuery({ queryKey: ["public-event-website", makerspaceSlug, publicToken],
    queryFn: () => tenantPublicRequest<EventWebsite>(makerspaceSlug, `/public/${encodeURIComponent(makerspaceSlug)}/events/${encodeURIComponent(publicToken)}/website/`),
    enabled: Boolean(allowed && makerspaceSlug && publicToken), staleTime: 0, gcTime: 0,
    refetchOnMount: "always", refetchInterval: 30_000, refetchOnWindowFocus: true,
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });
  const page = query.error ? undefined : query.data;
  const base = path(`events/${encodeURIComponent(publicToken)}`);
  const links: WebsiteLinks = { schedule: `${base}/schedule`, speaker: (value) => `${base}/speakers/${encodeURIComponent(value)}`, session: (value) => `${base}/sessions/${encodeURIComponent(value)}` };
  const speaker = page?.sections.find((row) => row.kind === "speaker" && row.slug === speakerSlug && row.visibility === "published");
  const session = page?.sessions.find((row) => row.slug === sessionSlug && row.visibility === "published");
  const visible = allowed && page && page.section_enabled?.[view === "speaker" ? "SPEAKERS" : "SCHEDULE"] !== false && (view === "schedule" || (view === "speaker" ? speaker : session));
  const title = view === "schedule" ? "Event schedule" : speaker?.title ?? session?.title ?? "Event website";
  const image = (url: string, alt: string) => <PublicWebsiteImage makerspaceSlug={makerspaceSlug} url={url} alt={alt} />;
  return <main className="desk-shell min-h-screen p-5"><SkipLink /><div id="main-content" className="mx-auto grid max-w-3xl gap-4">
    <Link className="desk-button w-fit" to={base}>Back to event</Link>
    {query.isLoading && allowed ? <p role="status">Loading event website…</p> : null}
    {!allowed || page && !visible || query.error ? <p role="alert">{query.error && !(query.error instanceof StructuredApiError && query.error.status === 404) ? "Unable to load this event website." : "Page not found."}</p> : null}
    {query.error ? <button className="desk-button w-fit" onClick={() => query.refetch()}>Retry</button> : null}
    {visible && page ? <><PageMetadata title={title} description={(speaker?.body ?? session?.body ?? "Event programme").slice(0, 200)} path={location.pathname} /><h1 className="title-page">{title}</h1>
      {view === "speaker" && speaker ? <><section><h2 className="title-section">Speaker profile</h2><WebsiteSectionCard row={speaker} image={image} /></section>{page.section_enabled?.SCHEDULE !== false && page.sessions.some((row) => row.speakers.includes(speaker.slug)) ? <WebsiteProgramme website={page} links={links} sessions={page.sessions.filter((row) => row.speakers.includes(speaker.slug))} /> : null}</> : <WebsiteProgramme website={page} links={links} sessions={view === "session" && session ? [session] : page.sessions} />}
    </> : null}
  </div></main>;
}

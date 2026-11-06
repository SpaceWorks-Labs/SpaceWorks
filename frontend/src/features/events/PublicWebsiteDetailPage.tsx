import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { PublicWebsiteImage } from "../../components/PublicWebsiteImage";
import { PageMetadata } from "../../components/PageMetadata";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { WebsiteProgramme, WebsiteSectionCard, type WebsiteLinks } from "./PublicEventWebsite";
import { markdownMode, type PublicEventWebsiteData } from "./websiteTypes";
import { markdownExcerpt } from "../../components/restrictedMarkdownTokens";
import { surfaceOf } from "./publicSurface";

/** Read the current gated projection rather than retaining a detached speaker/session snapshot. */
export function PublicWebsiteDetailPage({ view }: { view: "schedule" | "session" | "speaker" }) {
  const { slug, publicToken = "", sessionSlug, speakerSlug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const path = useTenantPath(makerspaceSlug);
  const location = useLocation();
  const allowed = tenant.mode !== "single" || !slug || slug === tenant.slug;
  // Same chrome contract as the event detail page this view is reached from (and shares its cached bootstrap).
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central" && allowed);
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const query = useQuery({ queryKey: ["public-event-website", makerspaceSlug, publicToken],
    queryFn: () => tenantPublicRequest<PublicEventWebsiteData>(makerspaceSlug, `/public/${encodeURIComponent(makerspaceSlug)}/events/${encodeURIComponent(publicToken)}/website/`),
    enabled: Boolean(allowed && makerspaceSlug && publicToken), staleTime: 0, gcTime: 0,
    refetchOnMount: "always", refetchInterval: 30_000, refetchOnWindowFocus: true,
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });
  // The website sub-pages of an UNLISTED event are noindex like its main page (L1, G2).
  const detail = useQuery({ queryKey: ["public-event", makerspaceSlug, publicToken], retry: false, staleTime: 30_000,
    queryFn: () => tenantPublicRequest<object>(makerspaceSlug, `/public/${encodeURIComponent(makerspaceSlug)}/events/${encodeURIComponent(publicToken)}/`),
    enabled: Boolean(allowed && makerspaceSlug && publicToken) });
  const noindex = surfaceOf(detail.data).indexable === false;
  const page = query.error ? undefined : query.data;
  const base = path(`events/${encodeURIComponent(publicToken)}`);
  const links: WebsiteLinks = { schedule: `${base}/schedule`, speaker: (value) => `${base}/speakers/${encodeURIComponent(value)}`, session: (value) => `${base}/sessions/${encodeURIComponent(value)}` };
  const speaker = page?.sections.find((row) => row.kind === "speaker" && row.slug === speakerSlug && row.visibility === "published");
  const session = page?.sessions.find((row) => row.slug === sessionSlug && row.visibility === "published");
  const visible = allowed && page && page.section_enabled?.[view === "speaker" ? "SPEAKERS" : "SCHEDULE"] !== false && (view === "schedule" || (view === "speaker" ? speaker : session));
  const title = view === "schedule" ? "Event schedule" : speaker?.title ?? session?.title ?? "Event website";
  const image = (url: string, alt: string) => <PublicWebsiteImage makerspaceSlug={makerspaceSlug} url={url} alt={alt} />;
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const failed = !allowed || (page && !visible) || query.error;
  const state = query.isLoading && allowed ? { status: "loading" as const } : failed ? { status: "error" as const,
    error: query.error && !(query.error instanceof StructuredApiError && query.error.status === 404) ? t`Unable to load this event website.` : t`Page not found.`,
    onRetry: query.error ? () => { void query.refetch(); } : undefined } : { status: "ready" as const };
  return <div style={brandStyle}>
    {visible && page ? <PageMetadata title={title} description={markdownExcerpt(speaker?.body ?? session?.body ?? "Event programme", markdownMode(speaker?.body_rendering ?? session?.body_rendering))} path={location.pathname} noindex={noindex} /> : null}
    <PublicLayout {...publicPageChrome(makerspaceSlug, name, path, bootstrap)} state={state} width="narrow"
      breadcrumb={[{ label: t`All events`, href: path("events") }, { label: t`Back to event`, href: base }, { label: visible ? title : t`Event website` }]}
      header={{ eyebrow: view === "schedule" ? undefined : view === "speaker" ? t`Speaker` : t`Session`, title: visible ? title : t`Event website` }}>
      {visible && page ? <div className="grid gap-8">
        {view === "speaker" && speaker ? <><section aria-label={t`Speaker profile`} className="grid gap-3"><h2 className="title-panel">{t`Speaker profile`}</h2><WebsiteSectionCard row={speaker} image={image} /></section>{page.section_enabled?.SCHEDULE !== false && page.sessions.some((row) => (row.speakers ?? []).includes(speaker.slug)) ? <WebsiteProgramme website={page} links={links} sessions={page.sessions.filter((row) => (row.speakers ?? []).includes(speaker.slug))} /> : null}</> : <WebsiteProgramme website={page} links={links} sessions={view === "session" && session ? [session] : page.sessions} />}
      </div> : null}
    </PublicLayout>
  </div>;
}

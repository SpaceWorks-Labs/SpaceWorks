import { t } from "@lingui/core/macro";
import { ClosedNoticeBanner } from "./ClosedNoticeBanner";
import { OpenNowIndicator } from "./OpenNowIndicator";
import { useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import type { Action } from "../../components/ui";
import { publicFamilies, preferredPublicFamily, type PublicFamily } from "../../lib/publicHome";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { FeaturedActivities } from "./FeaturedActivities";
import { MakerspaceHeader } from "./MakerspaceHeader";
import { ContactSection, MachinesSection, MembershipSection, SpacesSection } from "./MakerspaceMoreSections";
import { PublicDayPasses } from "../guestPasses/public/PublicDayPasses";
import { MakerspaceAreas } from "./MakerspaceAreas";
import { usePublicPage } from "../publicPages/pageApi";
import { PublicPageHero } from "../publicPages/PublicPageHero";
import { PublicPageSections } from "../publicPages/PublicPageSections";
import { PageShare } from "../publicPages/PageShare";
import { PageImage } from "../publicPages/PageImage";
import { usePageBranding } from "../publicPages/usePageBranding";
import { NotFoundPage } from "../NotFoundPage";
import { StructuredApiError } from "../../lib/api";
import { ErrorBlock } from "../../components/ui";
import { nounTitleOf, spaceKindOf } from "../../lib/spaceNoun";

/**
 * The public makerspace overview keeps published content and enabled activities together.
 * Inventory listings and requests belong exclusively to the separate inventory page.
 */
export function MakerspacePage({ profileSlug, profileOnly = false }: { profileSlug?: string; profileOnly?: boolean } = {}) {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = profileSlug ?? (tenant.mode === "single" ? tenant.slug : slug ?? "");
  const path = useTenantPath(makerspaceSlug);
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const pageQuery = usePublicPage("makerspace", makerspaceSlug);
  // A failed refetch keeps the last published page (404s resolve to null, not an error).
  const published = pageQuery.data ?? undefined;
  const pageStyle = usePageBranding(published?.presentation.resolved_theme ?? bootstrap?.theme, published?.presentation.accent_choice);
  if (profileOnly && (pageQuery.data === null || pageQuery.error instanceof StructuredApiError && pageQuery.error.status === 404)) return <NotFoundPage />;
  // The route chooses this page only once bootstrap is known; nothing to compose before then.
  if (!bootstrap) return null;
  const families = new Set(publicFamilies(bootstrap));
  const name = bootstrap.branding.display_name || bootstrap.makerspace.name || formatSlug(makerspaceSlug) || nounTitleOf(bootstrap.makerspace);
  const chrome = publicPageChrome(makerspaceSlug, name, path, bootstrap);
  const preferred = preferredPublicFamily(bootstrap);
  const shortcuts: Record<PublicFamily, Action> = {
    inventory: { label: t`Browse inventory`, href: path("inventory") },
    events: { label: t`See events`, href: path("events") },
    bookings: { label: t`Book a space`, href: path("bookings") },
    machines: { label: t`See machines`, href: path("machines") },
    membership: { label: t`Member area`, href: path("member") },
  };
  const ordered = [...families].sort((a, b) => Number(b === preferred) - Number(a === preferred));
  const actions = ordered.map(family => shortcuts[family]);
  const functional = <div className="grid gap-8">
    <ClosedNoticeBanner bootstrap={bootstrap} />
    <OpenNowIndicator bootstrap={bootstrap} />
    {families.has("events") ? <FeaturedActivities slug={makerspaceSlug} path={path} timeZone={bootstrap.makerspace.timezone} /> : null}
    <MakerspaceAreas links={chrome.nav.filter(link => link.href !== path())} />
    {families.has("machines") ? <MachinesSection path={path} /> : null}
    {families.has("bookings") ? <SpacesSection slug={makerspaceSlug} path={path} /> : null}
    {families.has("membership") ? <MembershipSection policy={bootstrap.makerspace.membership_policy} path={path} /> : null}
    {families.has("membership") && bootstrap.features?.includes("membership.day_passes") ? <PublicDayPasses slug={makerspaceSlug} memberHref={path("member")} /> : null}
  </div>;
  const page = <PublicLayout {...chrome} width="wide" state={{ status: "ready" }}
    hero={published ? <PublicPageHero page={published} slug={makerspaceSlug} actions={actions} bannerUrl={bootstrap.makerspace.cover_image_url} /> : <MakerspaceHeader name={name} bootstrap={bootstrap} actions={actions} />}>
    {published ? <div className="grid gap-8"><PublicPageSections sections={published.sections} functional={functional} token={published.publication_token} slug={makerspaceSlug}
      image={(url, alt) => <PageImage url={url} alt={alt} slug={makerspaceSlug} token={published.publication_token} />} />
      <PageShare title={published.title} description={published.description} canonicalUrl={published.canonical_url} image={published.cover ? <PageImage url={published.cover.url} alt={published.cover.alt} slug={makerspaceSlug} token={published.publication_token} /> : undefined} /></div> : <>{functional}<ContactSection bootstrap={bootstrap} /></>}
  </PublicLayout>;

  // Only the profile-only route depends on the page endpoint. The overview never
  // gives way to a transient page-endpoint error; it simply renders as unpublished.
  if (profileOnly && !published && pageQuery.error) return <PublicLayout {...publicPageChrome(makerspaceSlug, name, path, bootstrap)} header={{ title: t`Public page` }} state={{ status: "ready" }}><ErrorBlock error={pageQuery.error} onRetry={() => { void pageQuery.refetch(); }} /></PublicLayout>;
  if (profileOnly && !published) return <PublicLayout {...publicPageChrome(makerspaceSlug, name, path, bootstrap)} header={{ title: name }} state={{ status: "loading" }}><span /></PublicLayout>;
  return <div style={published ? pageStyle : brandStyle}>
    <PageMetadata title={published?.title ?? name} description={published?.description ?? (bootstrap.branding.welcome_body || (spaceKindOf(bootstrap.makerspace) === "organization" ? t`Events, rooms and membership with ${name}.` : t`Events, tools and spaces at ${name}.`))} path={published?.canonical_url ?? path()}
      image={published?.cover?.url ?? (published ? null : bootstrap.makerspace.cover_image_url || bootstrap.makerspace.logo_url)} imageAlt={published?.cover?.alt} siteName={name} />
    {page}
  </div>;
}

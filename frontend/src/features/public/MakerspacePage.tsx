import type { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import type { PublicActionCardProps } from "../../components/layouts/PublicActionCard";
import { PageMetadata } from "../../components/PageMetadata";
import type { Action } from "../../components/ui";
import { publicFamilies } from "../../lib/publicHome";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { PublicInventoryPage } from "../inventory/PublicInventoryPage";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { formatSlug } from "../inventory/PublicInventoryParts";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { FeaturedActivities } from "./FeaturedActivities";
import { MakerspaceHeader } from "./MakerspaceHeader";
import { ContactSection, MachinesSection, MembershipSection, SpacesSection } from "./MakerspaceMoreSections";
import { MakerspaceSection } from "./MakerspaceSection";
import { usePublicPage } from "../publicPages/pageApi";
import { PublicPageHero } from "../publicPages/PublicPageHero";
import { PublicPageSections } from "../publicPages/PublicPageSections";
import { PageShare } from "../publicPages/PageShare";
import { PageImage } from "../publicPages/PageImage";
import { usePageBranding } from "../publicPages/usePageBranding";
import { NotFoundPage } from "../NotFoundPage";
import { StructuredApiError } from "../../lib/api";
import { ErrorBlock } from "../../components/ui";

/**
 * The public makerspace page at /m/<slug>: header, Featured activities, Inventory, then the other
 * public sections. Every section is gated here on the same module and publication flags that gate
 * its own full page (`publicFamilies`), so a section never links to a page that would 404.
 * The catalogue is the existing public browse, embedded unchanged, so its visibility rules
 * (no storage locations, box ids, QR codes or hidden counts) stay owned by the inventory feature.
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
  const published = pageQuery.error ? undefined : pageQuery.data;
  const pageStyle = usePageBranding(published?.presentation.resolved_theme ?? bootstrap?.theme, published?.presentation.accent_choice);
  if (profileOnly && (pageQuery.isSuccess && !pageQuery.data || pageQuery.error instanceof StructuredApiError && pageQuery.error.status === 404)) return <NotFoundPage />;
  // The route chooses this page only once bootstrap is known; nothing to compose before then.
  if (!bootstrap) return null;
  const families = new Set(publicFamilies(bootstrap));
  const name = bootstrap.branding.display_name || bootstrap.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const actions: Action[] = [];
  if (families.has("inventory")) actions.push({ label: "Browse inventory", href: "#inventory" });
  if (families.has("events")) actions.push({ label: "See events", href: path("events") });
  if (families.has("bookings")) actions.push({ label: "Book a space", href: path("bookings") });
  if (families.has("membership")) actions.push({ label: "Member area", href: path("member") });

  const functional = (catalogue?: { body: ReactNode; aside: PublicActionCardProps }) => <div className="grid gap-8">
    {families.has("events") ? <FeaturedActivities slug={makerspaceSlug} path={path} timeZone={bootstrap.makerspace.timezone} /> : null}
    {catalogue ? <MakerspaceSection id="inventory" title="Inventory" subtitle="Tools, kits and materials you can borrow.">{catalogue.body}</MakerspaceSection> : null}
    {families.has("machines") ? <MachinesSection path={path} /> : null}
    {families.has("bookings") ? <SpacesSection slug={makerspaceSlug} path={path} /> : null}
    {families.has("membership") ? <MembershipSection policy={bootstrap.makerspace.membership_policy} path={path} /> : null}
  </div>;
  const page = (catalogue?: { body: ReactNode; aside: PublicActionCardProps }) =>
    <PublicLayout {...publicPageChrome(makerspaceSlug, name, path, bootstrap)} width="wide" state={{ status: "ready" }}
      hero={published ? <PublicPageHero page={published} slug={makerspaceSlug} actions={actions} /> : <MakerspaceHeader name={name} bootstrap={bootstrap} actions={actions} />} aside={catalogue?.aside}>
      {published ? <div className="grid gap-8"><PublicPageSections sections={published.sections} functional={functional(catalogue)} token={published.publication_token} slug={makerspaceSlug}
        image={(url, alt) => <PageImage url={url} alt={alt} slug={makerspaceSlug} token={published.publication_token} />} />
        <PageShare title={published.title} description={published.description} canonicalUrl={published.canonical_url} image={published.cover ? <PageImage url={published.cover.url} alt={published.cover.alt} slug={makerspaceSlug} token={published.publication_token} /> : undefined} /></div> : <>{functional(catalogue)}<ContactSection bootstrap={bootstrap} /></>}
    </PublicLayout>;

  const failed = pageQuery.error && !(pageQuery.error instanceof StructuredApiError && pageQuery.error.status === 404);
  if (failed) return <PublicLayout {...publicPageChrome(makerspaceSlug, name, path, bootstrap)} header={{ title: "Public page" }} state={{ status: "ready" }}><ErrorBlock error={pageQuery.error} onRetry={() => { void pageQuery.refetch(); }} /></PublicLayout>;
  if (profileOnly && !published) return <PublicLayout {...publicPageChrome(makerspaceSlug, name, path, bootstrap)} header={{ title: name }} state={{ status: "loading" }}><span /></PublicLayout>;
  return <div style={published ? pageStyle : brandStyle}>
    <PageMetadata title={published?.title ?? name} description={published?.description ?? (bootstrap.branding.welcome_body || `Events, tools and spaces at ${name}.`)} path={published?.canonical_url ?? path()}
      image={published?.cover?.url ?? (published ? null : bootstrap.makerspace.cover_image_url || bootstrap.makerspace.logo_url)} imageAlt={published?.cover?.alt} siteName={name} />
    {families.has("inventory") ? <PublicInventoryPage key={makerspaceSlug} resolvedSlug={makerspaceSlug} embedded={({ body, aside }) => page({ body, aside })} /> : page()}
  </div>;
}

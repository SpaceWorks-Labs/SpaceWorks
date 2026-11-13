import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import { ThemeToggle } from "../../components/ThemeToggle";
import { StructuredApiError } from "../../lib/api";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { NotFoundPage } from "../NotFoundPage";
import { PageImage } from "../publicPages/PageImage";
import { PageShare } from "../publicPages/PageShare";
import { PublicPageHero } from "../publicPages/PublicPageHero";
import { PublicPageSections } from "../publicPages/PublicPageSections";
import { usePublicPage } from "../publicPages/pageApi";
import { usePageBranding } from "../publicPages/usePageBranding";
import { OrganizationPublicEvents, OrganizationPublicSpaces } from "./OrganizationPublicCollections";
import { usePublicOrganization } from "./publicOrganizationsApi";
import { OrganizationPlans } from "./OrganizationPlans";
import { OrganizationWorkspaceSections } from "./OrganizationWorkspace";
import { useOrganizationDirectoryEnabled } from "./publicDirectoryApi";
import { useOptionalTenant } from "../../lib/tenant";
import { CanonicalPageRedirect } from "../publicPages/CanonicalPageRedirect";

export function PublicOrganizationPage({ profileSlug, profileOnly = false }: { profileSlug?: string; profileOnly?: boolean } = {}) {
  const { organizationSlug = "" } = useParams();
  const slug = profileSlug ?? organizationSlug;
  const organization = usePublicOrganization(slug);
  const tenant = useOptionalTenant();
  const projection = usePublicPage("organization", slug);
  // A failed refetch keeps the last published page; 404s resolve to null rather than an error.
  const page = projection.data ?? undefined;
  const legacy = organization.error ? undefined : organization.data;
  const style = usePageBranding(page?.presentation.resolved_theme, page?.presentation.accent_choice);
  // The directory link shows only while the server lists organizations (404 = switched off).
  const directory = useOrganizationDirectoryEnabled();
  const pageMissing = projection.data === null || projection.error instanceof StructuredApiError && projection.error.status === 404;
  if (profileOnly && pageMissing || pageMissing && organization.error instanceof StructuredApiError && organization.error.status === 404) return <NotFoundPage />;
  // The legacy API owns adoption/withdrawal; cached consented prose never fills an unavailable builder.
  const error = projection.error && projection.data === undefined && !pageMissing ? projection.error : page ? null : organization.error;
  const ready = Boolean(page || pageMissing && legacy && !profileOnly);
  const name = ready ? page?.title ?? legacy?.name ?? t`Organization` : t`Organization`;
  // Global profiles belong on the platform frontend, even when their read API admits a tenant browser origin.
  if (tenant?.mode === "single" && ready) {
    try {
      const canonical = new URL(page?.canonical_url ?? legacy?.canonical_url ?? "");
      if (!["https:", "http:"].includes(canonical.protocol) || canonical.username || canonical.password) return <NotFoundPage />;
      if (canonical.origin !== window.location.origin) return <CanonicalPageRedirect url={canonical.href} />;
    } catch { return <NotFoundPage />; }
  }
  return <div style={style}><PublicLayout makerspace={{ name, logo: legacy?.logo_url || undefined, slug: "", homeHref: "/" }}
    nav={[{ label: t`Directory`, href: "/" }, ...(directory ? [{ label: t`Organizations`, href: "/organizations" }] : [])]} headerAction={{ label: t`Sign in`, href: "/member" }} liveStatus={<ThemeToggle />}
    hero={page ? <PublicPageHero page={page} /> : <header className="mb-6"><p className="eyebrow">{t`Organization`}</p><h1 className="title-page">{name}</h1>{ready ? <><p className="mt-3 text-muted">{legacy?.description}</p>{legacy?.website ? <a className="desk-button mt-3" href={legacy.website} rel="noopener noreferrer">{t`Visit website`}</a> : null}</> : null}</header>}
    state={error ? { status: "error", error: error instanceof Error ? error.message : t`Couldn't load organization.`, onRetry: () => { void projection.refetch(); void organization.refetch(); } } : ready ? { status: "ready" } : { status: "loading" }}
    footer={{ credit: "Powered by Space Works", links: [{ label: t`About`, href: "/about" }, { label: t`License`, href: LICENSE_URL, external: true }, { label: t`Staff sign-in`, href: "/admin" }] }}>
    <div className="grid gap-8">
      {ready ? <PageMetadata title={name} description={page?.description ?? legacy?.description ?? ""} path={page?.canonical_url ?? legacy?.canonical_url ?? `/o/${slug}`} image={page ? page.cover?.url : legacy?.logo_url} imageAlt={page?.cover?.alt} /> : null}
      {page ? <PublicPageSections sections={page.sections} token={page.publication_token} linkedMakerspaces={<OrganizationPublicSpaces slug={slug} token={page.publication_token} />}
        organizationCollections={<OrganizationPublicEvents slug={slug} token={page.publication_token} />}
        image={(url, alt) => <PageImage url={url} alt={alt} token={page.publication_token} />} />
        : ready ? <><section aria-label={t`Linked makerspaces`} className="grid gap-4"><h2 className="title-panel">{t`Linked makerspaces`}</h2><OrganizationPublicSpaces slug={slug} /></section><section aria-label={t`Organization events`} className="grid gap-4"><h2 className="title-panel">{t`Organization events`}</h2><OrganizationPublicEvents slug={slug} /></section></> : null}
      {ready && legacy?.workspace && legacy.home_space ? <OrganizationWorkspaceSections workspace={legacy.workspace} spaceSlug={legacy.home_space.slug} /> : null}
      {ready && legacy ? <OrganizationPlans organization={legacy} workspace={Boolean(legacy.workspace)} /> : null}
      {page ? <PageShare title={page.title} description={page.description} canonicalUrl={page.canonical_url} image={page.cover ? <PageImage url={page.cover.url} alt={page.cover.alt} token={page.publication_token} /> : undefined} /> : null}
    </div>
  </PublicLayout></div>;
}

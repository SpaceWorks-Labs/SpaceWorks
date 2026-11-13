import { t } from "@lingui/core/macro";
import { useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import { ThemeToggle } from "../../components/ThemeToggle";
import { formatDate } from "../../lib/format";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { LICENSE_URL, publicPageChrome } from "../inventory/PublicPageChrome";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { LegalMarkdown, splitTitle } from "./LegalMarkdown";
import { legalTitle, useLegalPage, type LegalSlug } from "./legalApi";

/**
 * /privacy and /terms (parity A13): the space's own text on a space's pages, otherwise the operator's,
 * otherwise the shipped default. Read-only Markdown; editing lives in the consoles.
 */
export function LegalPage({ slug }: { slug: LegalSlug }) {
  const params = useParams();
  const tenant = useTenant();
  const space = tenant.mode === "single" ? tenant.slug : params.slug ?? "";
  const path = useTenantPath(space);
  const bootstrapQuery = useTenantBootstrap(space, tenant.mode === "central" && Boolean(space));
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const page = useLegalPage(slug, space);
  const split = splitTitle(page.data?.markdown ?? "");
  const title = split.title || legalTitle(slug);
  const other: LegalSlug = slug === "privacy" ? "terms" : "privacy";
  const spaceName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || "";
  const chrome = space
    ? publicPageChrome(space, spaceName || space, path, bootstrap)
    : { makerspace: { name: "Space Works", slug: "", homeHref: "/" }, nav: [{ label: t`Home`, href: "/" }],
      headerAction: { label: t`Sign in`, href: "/member" }, liveStatus: <ThemeToggle variant="icon" />,
      footer: { credit: "Powered by Space Works", links: [{ label: t`About`, href: "/about" }, { label: t`License`, href: LICENSE_URL, external: true }] } };
  const updated = page.data?.updated_at ? t`Last updated ${formatDate(page.data.updated_at)}.` : undefined;
  return <>
    <PageMetadata title={spaceName ? `${title} · ${spaceName}` : title} description={legalTitle(slug)} path={space ? path(slug) : `/${slug}`} />
    <PublicLayout {...chrome} width="narrow"
      header={{ title, subtitle: updated, secondary: { label: legalTitle(other), href: space ? path(other) : `/${other}` } }}
      state={page.isLoading ? { status: "loading" } : page.error ? { status: "error", error: t`This page could not be loaded. Try again.`, onRetry: () => { void page.refetch(); } } : { status: "ready" }}>
      {page.data ? <article aria-label={title}><LegalMarkdown body={split.body} /></article> : null}
    </PublicLayout>
  </>;
}

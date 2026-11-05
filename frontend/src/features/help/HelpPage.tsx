import { useLocation, useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import { ThemeToggle } from "../../components/ThemeToggle";
import { useTenant } from "../../lib/tenant";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { NotFoundPage } from "../NotFoundPage";
import { visibleArticles } from "./helpAudience";
import { helpArticle, helpArticles } from "./helpContent";
import { HELP_FEATURE, helpHref, platformSearch, type HelpLocation } from "./helpPaths";
import { SECTION_BY_ID } from "./helpSections";
import type { HelpSpace } from "./helpTypes";
import { HelpArticleView } from "./HelpArticleView";
import { HelpIndex } from "./HelpIndex";
import { useHelpReader } from "./useHelpReader";

/**
 * The in-app guide (#69, #128 C-31). `/help` on a single-space origin and `/m/<slug>/help` on
 * the central one belong to that space: its `platform.help_centre` switch turns them off, and
 * its module switches hide articles it cannot use. The central `/help` is the platform guide.
 */
export function HelpPage() {
  const { slug: routeSlug = "", sectionId = "", articleSlug = "" } = useParams();
  const tenant = useTenant();
  const { search } = useLocation();
  const platform = platformSearch(search);
  const single = tenant.mode === "single";
  const bootstrapQuery = useTenantBootstrap(routeSlug, !single && Boolean(routeSlug));
  const bootstrap = single ? tenant.bootstrap : routeSlug ? bootstrapQuery.data : null;
  const { reader, loading: readerLoading } = useHelpReader(platform);
  const spaceLoading = single ? tenant.loading : Boolean(routeSlug) && bootstrapQuery.isLoading;

  const where: HelpLocation = { slug: single ? null : routeSlug || null, platform };
  const spaceName = bootstrap ? bootstrap.branding.display_name || bootstrap.makerspace.name : "Space Works";
  const homeHref = single ? "/" : routeSlug ? `/m/${encodeURIComponent(routeSlug)}` : "/";
  const memberHref = single || !routeSlug ? "/member" : `/m/${encodeURIComponent(routeSlug)}/member`;
  const chrome = {
    makerspace: { name: spaceName, slug: bootstrap?.makerspace.slug ?? routeSlug, homeHref, logo: bootstrap?.branding.logo_url || undefined },
    nav: [{ label: "Help", href: helpHref("", where) }, ...(bootstrap ? [{ label: spaceName, href: homeHref }] : [])],
    headerAction: reader.signedIn ? { label: "Your account", href: memberHref } : { label: "Sign in", href: memberHref },
    liveStatus: <ThemeToggle variant="icon" />,
    width: "narrow" as const,
    footer: { credit: "Space Works help centre", links: [{ label: "About Space Works", href: "/about" }] },
  };

  if (routeSlug && bootstrapQuery.isError) return <NotFoundPage />;
  if (spaceLoading) {
    return <PublicLayout {...chrome} header={{ title: "Help" }} state={{ status: "loading" }}><span /></PublicLayout>;
  }
  // The space switched its help centre off: its help routes are gone, like any other off feature.
  if (bootstrap && !bootstrap.features.includes(HELP_FEATURE)) return <NotFoundPage />;

  const space: HelpSpace | null = bootstrap ? { slug: bootstrap.makerspace.slug, modules: bootstrap.modules, features: bootstrap.features } : null;
  const articles = visibleArticles(helpArticles(), reader, space);
  const hrefFor = (target: string) => helpHref(target, where);

  if (articleSlug) {
    const id = `${sectionId}/${articleSlug}`;
    const article = helpArticle(id);
    const section = SECTION_BY_ID.get(sectionId);
    return <>
      <PageMetadata title={`${article?.title ?? "Help"} · ${spaceName} help`} description={article?.summary ?? ""} path={hrefFor(id)} />
      <HelpArticleView chrome={chrome} article={article} section={section} visible={articles.some(item => item.id === id)}
        loading={readerLoading} signedIn={reader.signedIn} memberHref={memberHref}
        siblings={articles.filter(item => item.section === sectionId && item.id !== id)} hrefFor={hrefFor} />
    </>;
  }
  return <>
    <PageMetadata title={`${spaceName} help`} description="Guides for members, staff and operators." path={hrefFor(sectionId)} />
    <HelpIndex chrome={chrome} articles={articles} sectionId={sectionId} loading={readerLoading} signedIn={reader.signedIn}
      memberHref={memberHref} hrefFor={hrefFor} spaceName={bootstrap ? spaceName : null} />
  </>;
}

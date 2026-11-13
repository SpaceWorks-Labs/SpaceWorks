import { plural, t } from "@lingui/core/macro";
import { useDeferredValue, useRef, useState } from "react";
import { PublicLayout } from "../../components/layouts";
import { PageMetadata } from "../../components/PageMetadata";
import { ThemeToggle } from "../../components/ThemeToggle";
import { FilterBar } from "../../components/ui";
import { PagePager } from "../../components/ui/PagePager";
import { LICENSE_URL } from "../inventory/PublicPageChrome";
import { SpaceCardSkeletons } from "../discover/spaces/SpaceCard";
import { NotFoundPage } from "../NotFoundPage";
import { DirectoryError, DirectoryState, OrganizationCard } from "./OrganizationDirectoryParts";
import { isDirectoryOff, usePublicOrganizationDirectory } from "./publicDirectoryApi";

/**
 * `/organizations` (PP1): the opt-in public directory. An organization is listed only when the
 * deployment switch is on and it chose to be discoverable with a public profile; the server answers
 * 404 otherwise, and so does this page. Search is by name on the server, 24 to a page.
 */
export function PublicOrganizationDirectory() {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const top = useRef<HTMLElement>(null);
  const search = useDeferredValue(query.trim().slice(0, 100));
  const list = usePublicOrganizationDirectory(page, search);
  if (isDirectoryOff(list.error)) return <NotFoundPage />;
  const rows = list.data?.results ?? [];
  const total = list.data?.count ?? 0;
  const turnPage = (next: number) => { setPage(next); top.current?.scrollIntoView?.({ block: "start" }); };

  let body;
  if (list.isError && !list.data) body = <DirectoryError onRetry={() => { void list.refetch(); }} retrying={list.isFetching} />;
  else if (list.isLoading) body = <SpaceCardSkeletons label={t`Loading organizations`} />;
  else if (!rows.length && search) body = <DirectoryState art="moods/empty" live="status" title={t`No organizations match “${search}”`}
    actions={<button type="button" className="desk-button" onClick={() => { setQuery(""); setPage(1); }}>{t`Clear search`}</button>}>
    <p>{t`Try a shorter or different name.`}</p>
  </DirectoryState>;
  else if (!rows.length) body = <DirectoryState art="moods/empty" live="status" title={t`No organizations listed yet`}>
    <p>{t`Organizations appear here once they publish a public profile and choose to be listed.`}</p>
  </DirectoryState>;
  else body = <>
    <ul className={rows.length <= 2 ? "sw-spaces-feature" : "sw-spaces-grid"} data-count={rows.length}>
      {rows.map(row => <li key={row.slug} className="flex min-w-0"><OrganizationCard row={row} /></li>)}
    </ul>
    <div className="mt-8"><PagePager page={page} setPage={turnPage} count={total} disabled={list.isFetching} /></div>
  </>;

  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }} chrome="canvas"
    nav={[{ label: t`Spaces`, href: "/spaces" }, { label: t`About`, href: "/about" }]} headerAction={{ label: t`Sign in`, href: "/member" }}
    liveStatus={<ThemeToggle variant="icon" />} state={{ status: "ready" }}
    hero={<section aria-labelledby="organizations-title" className="sw-field-citron sw-spaces-hero">
      <div className="sw-spaces-hero-copy">
        <h1 id="organizations-title" className="sw-spaces-hero-title">{t`Organizations on Space Works`}</h1>
        <p className="sw-hero-lede">{t`The clubs, schools, companies and networks behind the spaces: who they are and where they make.`}</p>
        <p className="min-h-5 text-sm font-semibold tabular-nums">{list.data ? plural(total, { one: "# organization", other: "# organizations" }) : null}</p>
      </div>
    </section>}
    footer={{ credit: "Space Works · Made for shared workshops", links: [{ label: t`Spaces`, href: "/spaces" }, { label: t`About`, href: "/about" },
      { label: t`License`, href: LICENSE_URL, external: true }, { label: t`Platform sign-in`, href: "/admin" }] }}>
    <PageMetadata title={t`Organizations`} description={t`Organizations that run or support makerspaces on Space Works.`} path="/organizations" />
    <section ref={top} aria-labelledby="organizations-directory-title" className="sw-spaces-directory">
      <h2 id="organizations-directory-title" className="sr-only">{t`All organizations`}</h2>
      <form role="search" className="sw-spaces-search" onSubmit={event => event.preventDefault()}>
        <FilterBar value={query} onChange={value => { setQuery(value); setPage(1); }} searchLabel={t`Search organizations`} placeholder={t`Search by name`} />
      </form>
      <div aria-busy={list.isFetching}>{body}</div>
    </section>
  </PublicLayout>;
}

import type { ReactElement, ReactNode } from "react";
import { MakerspaceBrand } from "../MakerspaceBrand";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { RouteLink } from "../ui/RouteLink";
import { ActionControl, PageHeader } from "../ui";
import type { Action, PageHeaderProps } from "../ui";
import { LayoutFrame, PublicQueryState, QueryContent } from "./LayoutFrame";
import { PublicActionCard, type PublicActionCardProps } from "./PublicActionCard";
import type { PublicDetailLayoutProps } from "./PublicDetailLayout";
import type { LayoutProps } from "./types";

// A chrome-only public wrapper delegates its one h1 and state display to its detail child.
type PublicBody = { header: PageHeaderProps; children: ReactNode; aside?: PublicActionCardProps }
  | { header?: never; children: ReactElement<PublicDetailLayoutProps>; aside?: never };
export type PublicLayoutProps = Omit<LayoutProps, "width"> & PublicBody & {
  makerspace: { name: string; logo?: string; slug: string; homeHref?: string };
  nav: { label: string; href: string }[];
  headerAction?: Action;
  liveStatus?: ReactNode;
  width?: "default" | "wide" | "narrow";
  breadcrumb?: { label: string; href?: string }[];
  footer: { credit?: string; links: Action[] };
};
export function PublicLayout({ makerspace, nav, headerAction, liveStatus, width = "default", breadcrumb, aside, children,
  footer, header, standalone = true, state, isEmpty, empty }: PublicLayoutProps) {
  const centralIdentity = !makerspace.slug && makerspace.name === "Space Works" && !makerspace.logo;
  const content = <div className={aside ? "sw-public-columns" : "min-w-0"}>
    <div className="min-w-0">{children}</div>{aside ? <PublicActionCard {...aside} /> : null}
  </div>;
  return <div className={`min-h-dvh bg-bg text-ink ${aside ? "pb-28 md:pb-0" : ""}`}>
    <header className="border-b border-line bg-panel">
      <div className="sw-layout sw-public-chrome flex flex-wrap items-center gap-4">
        <RouteLink href={makerspace.homeHref ?? `/m/${makerspace.slug}`} className={`min-w-0 flex-1 rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${centralIdentity ? "basis-full sm:basis-auto" : ""}`}>
          {centralIdentity ? <><span className="inline-flex sm:hidden"><SpaceWorksLogo variant="stacked" size={180} /></span>
            <span className="hidden sm:inline-flex"><SpaceWorksLogo variant="horizontal" size={288} /></span></>
            : <MakerspaceBrand name={makerspace.name} logoUrl={makerspace.logo} fallback="logo" className="w-full" />}
        </RouteLink>
        {headerAction ? <ActionControl action={headerAction} /> : <ActionControl action={{ label: "Sign in", href: `/m/${makerspace.slug}/member` }} />}
        <nav aria-label="Public navigation" className="order-last flex w-full min-w-0 gap-2 overflow-x-auto xl:order-none xl:w-auto">
          {nav.map(link => <ActionControl key={link.href} action={link} className="shrink-0 border-transparent" />)}
        </nav>
        {liveStatus}
      </div>
    </header>
    <LayoutFrame standalone={standalone} width={width} className={width === "narrow" ? "sw-public-narrow" : ""}>
      {breadcrumb?.length ? <nav aria-label="Breadcrumb" className="mb-6 flex flex-wrap items-center gap-2 text-sm">
        {breadcrumb.map((crumb, index) => <span key={`${crumb.label}-${index}`} className="flex items-center gap-2">
          {index ? <span aria-hidden="true">/</span> : null}{crumb.href ? <ActionControl action={{ label: crumb.label, href: crumb.href }} />
            : <span aria-current="page">{crumb.label}</span>}
        </span>)}
      </nav> : null}
      {header ? <><PageHeader {...header} /><QueryContent state={state} isEmpty={isEmpty} empty={empty}>{content}</QueryContent></>
        : <PublicQueryState.Provider value={{ state, isEmpty, empty }}>{content}</PublicQueryState.Provider>}
    </LayoutFrame>
    <footer className="border-t border-line">
      <div className="sw-layout sw-public-chrome flex flex-wrap items-center justify-between gap-4">
        <RouteLink href="/" className="inline-flex items-center gap-2 rounded-control text-sm text-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <SpaceWorksLogo variant="symbol" size={48} decorative /><span>{footer.credit ?? "Powered by Space Works"}</span>
        </RouteLink>
        <nav aria-label="Footer" className="flex flex-wrap gap-2">{footer.links.map(link => <ActionControl key={link.label} action={link} />)}</nav>
      </div>
    </footer>
  </div>;
}

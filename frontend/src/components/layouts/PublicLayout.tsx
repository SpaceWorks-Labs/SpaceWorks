import type { ReactElement, ReactNode } from "react";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { RouteLink } from "../ui/RouteLink";
import { ActionControl, PageHeader } from "../ui";
import { PublicHeader } from "./PublicHeader";
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
  const content = <div className={aside ? "sw-public-columns" : "min-w-0"}>
    <div className="min-w-0">{children}</div>{aside ? <PublicActionCard {...aside} /> : null}
  </div>;
  return <div className={`min-h-dvh bg-bg text-ink ${aside ? "pb-[calc(7rem+env(safe-area-inset-bottom))] md:pb-0" : ""}`}>
    <PublicHeader makerspace={makerspace} nav={nav} liveStatus={liveStatus}
      account={headerAction ?? { label: "Sign in", href: `/m/${makerspace.slug}/member` }} />
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
        <nav aria-label="Footer" className="flex min-w-0 flex-wrap gap-2">{footer.links.map(link => <ActionControl key={link.label} action={link} className="max-w-full [overflow-wrap:anywhere]" />)}</nav>
      </div>
    </footer>
  </div>;
}

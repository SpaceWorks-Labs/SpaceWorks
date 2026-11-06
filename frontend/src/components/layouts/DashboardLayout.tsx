import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { ActionControl, ActivityItem, ActivityRail, Callout, EmptyState, PageHeader, StatCard } from "../ui";
import type { Action, ActivityItemProps, CalloutProps, EmptyProps, PageHeaderProps, Stat } from "../ui";
import { RouteLink } from "../ui/RouteLink";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import { StaggerGroup } from "./StaggerGroup";
import type { LayoutProps } from "./types";
import { useLayoutMedia } from "./useLayoutMedia";

export type DashboardLayoutProps = LayoutProps & {
  header: PageHeaderProps & { eyebrow: string };
  callout?: CalloutProps;
  progress?: ReactNode;
  stats: Stat[];
  overflowStats?: { label: string; stats: Stat[] };
  main: { title: string; action?: Action; content: ReactNode; empty: EmptyProps; isEmpty?: boolean }[];
  rail?: { title: string; items: (ActivityItemProps & { key: string })[]; seeAll?: Action };
  railContent?: ReactNode;
};

// Secondary numbers stay visible (never hidden behind a disclosure): a quiet row per metric,
// zero muted, anything needing attention carried by the emphasis pill rather than colour alone.
function CompactStat({ label, value, tone, href }: Stat) {
  const attention = tone === "attention" || tone === "danger";
  const zero = value === 0 || value === "0";
  const body = <>
    <span className="min-w-0 truncate text-sm text-ink">{label}</span>
    {attention ? <span className="rounded-full bg-emphasis px-2.5 py-0.5 text-sm font-semibold tabular-nums text-on-emphasis">{value}</span>
      : <span className={`text-base font-semibold tabular-nums ${zero ? "text-muted" : "text-ink"}`}>{value}</span>}
  </>;
  const classes = "flex min-h-12 items-center justify-between gap-3 rounded-xl border border-line bg-panel px-4 py-2";
  return href ? <RouteLink href={href} className={`${classes} hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus`}
    aria-label={`${label}: ${value}`}>{body}</RouteLink> : <div className={classes}>{body}</div>;
}

export function DashboardLayout({ header, callout, progress, stats, overflowStats, main, rail, railContent,
  standalone, width, ...query }: DashboardLayoutProps) {
  const desktop = useLayoutMedia("(min-width: 1280px)");
  const overflow = [...stats.slice(4), ...(overflowStats?.stats ?? [])];
  return <LayoutFrame standalone={standalone} width={width}>
    <PageHeader {...header} />
    <QueryContent {...query}>
      <div className="grid gap-8">
        {callout ? <Callout {...callout} /> : null}
        {progress}
        {stats.length ? <StaggerGroup className="sw-stats">{stats.slice(0, 4).map(stat => <StatCard key={stat.label} {...stat} />)}</StaggerGroup> : null}
        {overflow.length ? <section aria-label={overflowStats?.label ?? t`More numbers`}>
          <h2 className="sr-only">{overflowStats?.label ?? t`More numbers`}</h2>
          <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{overflow.map(stat => <li key={stat.label}><CompactStat {...stat} /></li>)}</ul>
        </section> : null}
        <div className={rail || railContent ? "sw-columns" : "min-w-0"}>
          <StaggerGroup className="grid min-w-0 content-start gap-8">{main.map(section => <section key={section.title} aria-label={section.title}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="title-panel">{section.title}</h2>
              {section.action ? <ActionControl action={section.action} /> : null}
            </div>
            {section.isEmpty || section.content == null ? <EmptyState {...section.empty} /> : section.content}
          </section>)}</StaggerGroup>
          {rail || railContent ? <div className="sw-dashboard-rail grid min-w-0 content-start gap-6">{rail ? <div><ActivityRail title={rail.title}>
            {(desktop ? rail.items : rail.items.slice(0, 3)).map(({ key, ...item }) => <ActivityItem key={key} {...item} />)}
          </ActivityRail>{rail.seeAll ? <div className="mt-3"><ActionControl action={rail.seeAll} /></div> : null}</div> : null}{railContent}</div> : null}
        </div>
      </div>
    </QueryContent>
  </LayoutFrame>;
}

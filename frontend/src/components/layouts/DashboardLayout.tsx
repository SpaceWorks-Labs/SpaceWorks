import { useState, type ReactNode } from "react";
import { ActionControl, ActivityItem, ActivityRail, Callout, CollapsibleSection, EmptyState, PageHeader, StatCard } from "../ui";
import type { Action, ActivityItemProps, CalloutProps, EmptyProps, PageHeaderProps, Stat } from "../ui";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
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

export function DashboardLayout({ header, callout, progress, stats, overflowStats, main, rail, railContent,
  standalone, width, ...query }: DashboardLayoutProps) {
  const [expanded, setExpanded] = useState(false);
  const desktop = useLayoutMedia("(min-width: 1280px)");
  const overflow = [...stats.slice(4), ...(overflowStats?.stats ?? [])];
  return <LayoutFrame standalone={standalone} width={width}>
    <PageHeader {...header} />
    <QueryContent {...query}>
      <div className="grid gap-8">
        {callout ? <Callout {...callout} /> : null}
        {progress}
        {stats.length ? <div className="sw-stats">{stats.slice(0, 4).map(stat => <StatCard key={stat.label} {...stat} />)}</div> : null}
        {overflow.length ? <CollapsibleSection title={overflowStats?.label ?? "Everything else"} open={expanded} onToggle={() => setExpanded(!expanded)}>
          <div className="sw-stats p-4">{overflow.map(stat => <StatCard key={stat.label} {...stat} />)}</div>
        </CollapsibleSection> : null}
        <div className={rail || railContent ? "sw-columns" : "min-w-0"}>
          <div className="grid min-w-0 content-start gap-8">{main.map(section => <section key={section.title} aria-label={section.title}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="title-panel">{section.title}</h2>
              {section.action ? <ActionControl action={section.action} /> : null}
            </div>
            {section.isEmpty || section.content == null ? <EmptyState {...section.empty} /> : section.content}
          </section>)}</div>
          {rail || railContent ? <div className="sw-dashboard-rail grid min-w-0 content-start gap-6">{rail ? <div><ActivityRail title={rail.title}>
            {(desktop ? rail.items : rail.items.slice(0, 3)).map(({ key, ...item }) => <ActivityItem key={key} {...item} />)}
          </ActivityRail>{rail.seeAll ? <div className="mt-3"><ActionControl action={rail.seeAll} /></div> : null}</div> : null}{railContent}</div> : null}
        </div>
      </div>
    </QueryContent>
  </LayoutFrame>;
}

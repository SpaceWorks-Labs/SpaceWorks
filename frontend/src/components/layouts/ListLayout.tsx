import type { ReactNode } from "react";
import { ActionControl, BulkActionToolbar, Callout, PageHeader, Pagination, StatCard, Tabs } from "../ui";
import type { Action, CalloutProps, EmptyProps, PageHeaderProps, Stat, Tab } from "../ui";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import { ListFilters, type ListFiltersProps } from "./ListFilters";
import type { LayoutProps } from "./types";

export type ListLayoutProps = LayoutProps & {
  header: PageHeaderProps;
  callout?: CalloutProps;
  stats?: Stat[];
  tabs?: Tab[];
  activeTab?: string;
  onTabChange?: (key: string) => void;
  stickyPrimaryOnMobile?: boolean;
  filters?: ListFiltersProps;
  body: { kind: "rows"; rows: ReactNode } | { kind: "table"; table: ReactNode };
  bulkBar?: { count: number; primary?: Action; actions: Action[]; onClear: () => void };
  empty: EmptyProps;
  filteredEmpty?: EmptyProps;
  /** Caller knows whether its query has active filters, including URL-only filters. */
  filtered?: boolean;
  pagination?: { page: number; pageSize: number; count: number; onChange: (page: number) => void };
  rail?: ReactNode;
  detail?: ReactNode;
};

export function ListLayout({ header, callout, stats = [], tabs, activeTab, onTabChange, stickyPrimaryOnMobile, filters, body, bulkBar,
  empty, filteredEmpty, filtered, pagination, rail, detail, standalone, width, ...query }: ListLayoutProps) {
  const hasFilters = filtered ?? Boolean(filters?.search?.value || filters?.chips?.length);
  const panel = <>
      {filters ? <ListFilters {...filters} /> : null}
      <QueryContent {...query} empty={hasFilters && filteredEmpty ? filteredEmpty : empty}>
        <div className={rail ? "sw-columns" : "min-w-0"}>
          <div className={`grid min-w-0 content-start gap-6 ${bulkBar?.count ? "pb-28 md:pb-0" : ""}`}>
            {bulkBar?.count ? <div className="fixed inset-x-[max(1rem,env(safe-area-inset-left))] bottom-[calc(var(--shell-bottom-tabs,0px)+var(--shell-safe-bottom,env(safe-area-inset-bottom))+1rem)] z-20 md:static">
              <BulkActionToolbar selectedCount={bulkBar.count} onClear={bulkBar.onClear}
                actions={<>{bulkBar.primary ? <ActionControl action={bulkBar.primary} primary /> : null}{bulkBar.actions.map(action => <ActionControl key={action.label} action={action} />)}</>} />
            </div> : null}
            <div className="min-w-0">{body.kind === "rows" ? <div className="grid gap-3">{body.rows}</div> : body.table}</div>
            {pagination ? <Pagination {...pagination} totalPages={Math.ceil(pagination.count / Math.max(1, pagination.pageSize))} /> : null}
          </div>
          {rail ? <aside aria-label="List activity" className="min-w-0">{rail}</aside> : null}
        </div>
      </QueryContent>
  </>;
  return <LayoutFrame standalone={standalone} width={width}>
    <PageHeader {...header} stickyPrimaryOnMobile={stickyPrimaryOnMobile ?? header.stickyPrimaryOnMobile} />
    <div className="grid min-w-0 gap-6">
      {callout ? <Callout {...callout} /> : null}
      {query.state.status === "ready" && stats.length ? <div className="sw-stats">{stats.slice(0, 4).map(stat => <StatCard key={stat.label} {...stat} />)}</div> : null}
      {tabs?.length ? <Tabs tabs={tabs} activeKey={activeTab ?? tabs[0].key} onChange={onTabChange}>{panel}</Tabs> : panel}
    </div>
    {detail}
  </LayoutFrame>;
}

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DashboardLayout } from "../../components/layouts";
import { Card, DataTable, ProgressBar, StatusPill } from "../../components/ui";
import type { Makerspace } from "./panels/shared";
import { adminQueryState } from "./adminPresentation";
import { STICKY_FIRST_COLUMN } from "./matrixColumns";
import { getTenantUsage, usageAmount, type TenantUsage } from "./platformMonitoringApi";
import { useManagedPlans } from "./platformSpaces/plansApi";
import { SpacePlanUsage } from "./hostingPlan/SpacePlanUsage";
import { SpaceInvoices } from "./hostingPlan/SpaceInvoices";

export function UsageTable({ data }: { data: TenantUsage }) {
  return <div role="region" aria-label="Resource usage against effective limits"><DataTable data={data.resources} getRowId={row => row.key}
    columns={[
      { key: "label", header: "Resource", className: STICKY_FIRST_COLUMN },
      { key: "used", header: "Used", render: row => usageAmount(row.used, row.unit) },
      { key: "limit", header: "Limit", render: row => row.limit === null ? "Unlimited" : usageAmount(row.limit, row.unit) },
      { key: "percentage", header: "Allowance used", render: row => {
        const percentage = row.used !== null && row.limit !== null && row.limit > 0 ? row.used / row.limit * 100 : null;
        return <>{percentage === null ? "—" : `${percentage.toFixed(1)}%`}{row.used !== null && row.limit !== null && row.used > row.limit ? " · Over limit" : null}</>;
      } },
    ]} /></div>;
}

export function TenantUsagePanel({ makerspace }: { makerspace: Makerspace }) {
  const [showTable, setShowTable] = useState(false);
  const query = useQuery({ queryKey: ["makerspace-usage", makerspace.id], queryFn: () => getTenantUsage(makerspace.id), refetchInterval: 60_000 });
  // The managed limiter (#187A) exists only when /config says so; otherwise nothing of it renders.
  const managed = useManagedPlans();
  const planSections = managed ? [
    { title: "Hosting plan", content: <SpacePlanUsage makerspaceId={makerspace.id} />, empty: { message: "No plan information yet." } },
    { title: "Invoices", content: <SpaceInvoices makerspaceId={makerspace.id} />, empty: { message: "No hosting invoices yet." } },
  ] : [];
  return <DashboardLayout header={{ title: "Usage & limits", eyebrow: makerspace.name,
    subtitle: "Daily and monthly counters reset with their quota period.",
    secondary: { label: "Refresh usage", onClick: () => { void query.refetch(); }, disabled: query.isFetching, disabledReason: "Usage is refreshing." } }}
    state={adminQueryState(query, "usage")} stats={[]}
    main={[...planSections, ...(query.data ? [{ title: "Resource allowances", empty: { message: "No resource counters yet. Refresh usage to check again." },
      isEmpty: !query.data.resources.length,
      action: { label: showTable ? "Show as cards" : "Show as table", onClick: () => setShowTable(!showTable) },
      content: <>
        {!query.data.managed ? <p className="mb-6 text-sm text-muted">This self-hosted deployment has no managed resource limits. Storage accounting is only maintained in managed mode.</p> : null}
        {showTable ? <UsageTable data={query.data} /> : <div className="grid gap-4 sm:grid-cols-2">
          {query.data.resources.map(row => {
            const fraction = row.used !== null && row.limit !== null && row.limit > 0 ? row.used / row.limit : null;
            const over = row.used !== null && row.limit !== null && row.used > row.limit;
            return <Card key={row.key}><div className="grid gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="title-section capitalize">{row.label}</h3>
                {over ? <StatusPill label="Over limit" tone="danger" /> : fraction !== null && fraction >= 0.8 ? <StatusPill label="Near limit" tone="warn" /> : null}</div>
              <p className="text-sm text-muted"><span className="font-display text-2xl text-ink">{usageAmount(row.used, row.unit)}</span> of <span>{row.limit === null ? "Unlimited" : usageAmount(row.limit, row.unit)}</span></p>
              {fraction !== null ? <><ProgressBar value={fraction} tone={fraction > 1 ? "danger" : fraction >= 0.8 ? "warn" : "accent"} label={`${row.label} allowance used`} /><p className="tabular-nums text-sm text-muted">{(fraction * 100).toFixed(1)}%</p></> : null}
            </div></Card>;
          })}
        </div>}
      </> }] : [])]} />;
}

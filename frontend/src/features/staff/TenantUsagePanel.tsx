import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DashboardLayout } from "../../components/layouts";
import { Card, DataTable, ProgressBar, StatusPill } from "../../components/ui";
import type { Makerspace } from "./panels/shared";
import { adminQueryState } from "./adminPresentation";
import { STICKY_FIRST_COLUMN } from "./matrixColumns";
import { getTenantUsage, usageAmount, type TenantUsage } from "./platformMonitoringApi";
import { useManagedPlans } from "./platformSpaces/plansApi";
import { limitLabel } from "./platformSpaces/limitCopy";
import { SpacePlanUsage } from "./hostingPlan/SpacePlanUsage";
import { SpaceInvoices } from "./hostingPlan/SpaceInvoices";
import { SpaceLimitsUsage } from "./hostingPlan/SpaceLimitsUsage";

export function UsageTable({ data }: { data: TenantUsage }) {
  return <div role="region" aria-label={t`Resource usage against effective limits`}><DataTable data={data.resources} getRowId={row => row.key}
    columns={[
      { key: "label", header: t`Resource`, className: STICKY_FIRST_COLUMN, render: row => limitLabel(row.key, row.label) },
      { key: "used", header: t`Used`, render: row => usageAmount(row.used, row.unit) },
      { key: "limit", header: t`Limit`, render: row => row.limit === null ? t`Unlimited` : usageAmount(row.limit, row.unit) },
      { key: "percentage", header: t`Allowance used`, render: row => {
        const percentage = row.used !== null && row.limit !== null && row.limit > 0 ? row.used / row.limit * 100 : null;
        return <>{percentage === null ? "—" : `${percentage.toFixed(1)}%`}{row.used !== null && row.limit !== null && row.used > row.limit ? t` · Over limit` : null}</>;
      } },
    ]} /></div>;
}

export function TenantUsagePanel({ makerspace }: { makerspace: Makerspace }) {
  const [showTable, setShowTable] = useState(false);
  const query = useQuery({ queryKey: ["makerspace-usage", makerspace.id], queryFn: () => getTenantUsage(makerspace.id), refetchInterval: 60_000 });
  // The managed limiter (#187A) exists only when /config says so; otherwise nothing of it renders.
  const managed = useManagedPlans();
  // Decisions 281/284: limits apply to every space, own or hosted, so "Limits by area" never waits for plans.
  const planSections = [
    ...(managed ? [{ title: t`Hosting plan`, content: <SpacePlanUsage makerspaceId={makerspace.id} />, empty: { message: t`No plan information yet.` } }] : []),
    { title: t`Limits by area`, content: <SpaceLimitsUsage makerspaceId={makerspace.id} />, empty: { message: t`No limits are set for this space.` } },
    ...(managed ? [{ title: t`Invoices`, content: <SpaceInvoices makerspaceId={makerspace.id} />, empty: { message: t`No hosting invoices yet.` } }] : []),
  ];
  return <DashboardLayout header={{ title: t`Usage & limits`, eyebrow: makerspace.name,
    subtitle: t`Daily and monthly counters reset with their quota period.`,
    secondary: { label: t`Refresh usage`, onClick: () => { void query.refetch(); }, disabled: query.isFetching, disabledReason: t`Usage is refreshing.` } }}
    state={adminQueryState(query, "usage")} stats={[]}
    main={[...planSections, ...(query.data ? [{ title: t`Resource allowances`, empty: { message: t`No resource counters yet. Refresh usage to check again.` },
      isEmpty: !query.data.resources.length,
      action: { label: showTable ? t`Show as cards` : t`Show as table`, onClick: () => setShowTable(!showTable) },
      content: <>
        {!query.data.managed ? <p className="mb-6 text-sm text-muted">{t`Limits are not switched on for this install, so nothing here is capped. Storage use is counted only while limits are on.`}</p> : null}
        {showTable ? <UsageTable data={query.data} /> : <div className="grid gap-4 sm:grid-cols-2">
          {query.data.resources.map(row => {
            const fraction = row.used !== null && row.limit !== null && row.limit > 0 ? row.used / row.limit : null;
            const over = row.used !== null && row.limit !== null && row.used > row.limit;
            return <Card key={row.key}><div className="grid gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="title-section">{limitLabel(row.key, row.label)}</h3>
                {over ? <StatusPill label={t`Over limit`} tone="danger" /> : fraction !== null && fraction >= 0.8 ? <StatusPill label={t`Near limit`} tone="warn" /> : null}</div>
              <p className="text-sm text-muted"><span className="font-display text-2xl text-ink">{usageAmount(row.used, row.unit)}</span>{" "}{t({ comment: "Between the used amount and the limit, as in \"3 GB of 10 GB\"", message: "of" })}{" "}<span>{row.limit === null ? t`Unlimited` : usageAmount(row.limit, row.unit)}</span></p>
              {fraction !== null ? <><ProgressBar value={fraction} tone={fraction > 1 ? "danger" : fraction >= 0.8 ? "warn" : "accent"} label={t`${limitLabel(row.key, row.label)} allowance used`} /><p className="tabular-nums text-sm text-muted">{(fraction * 100).toFixed(1)}%</p></> : null}
            </div></Card>;
          })}
        </div>}
      </> }] : [])]} />;
}

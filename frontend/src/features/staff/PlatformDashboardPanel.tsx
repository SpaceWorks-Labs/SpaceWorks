import { plural, t } from "@lingui/core/macro";
import { Trans } from "@lingui/react/macro";
import { useQuery } from "@tanstack/react-query";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { DashboardLayout } from "../../components/layouts";
import { type CalloutProps, DataTable, EmptyState, KeyValueCard, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { adminQueryState } from "./adminPresentation";
import { getPlatformDashboard, getPlatformProblems, usageAmount, type Problem } from "./platformMonitoringApi";
import { UsageTable } from "./TenantUsagePanel";
import { PlatformAnalyticsPanels } from "./PlatformAnalyticsPanels";
import { PlatformQueuesTable } from "./platformConsole/PlatformQueuesTable";
import { PlatformSearch } from "./platformConsole/PlatformSearch";
import { limitLabel } from "./platformSpaces/limitCopy";

const spaceStateStatLabel = (state: string) => ({ active: t`Active spaces`, importing: t`Spaces importing`,
  aborted: t`Aborted imports`, suspended: t`Paused spaces`, archived: t`Archived spaces`, read_only: t`Read-only spaces`,
  scheduled: t`Spaces scheduled to change` } as Record<string, string>)[state]
  ?? t`Spaces: ${sentenceCase(state).toLowerCase()}`;
const offsiteStateLabel = (state: string) => ({ never: t`Never copied`, pending: t`Waiting to upload`, uploading: t`Uploading`,
  bytes_verified: t`Copy verified`, abandoned: t`Abandoned`, deleted: t`Removed by retention` } as Record<string, string>)[state]
  ?? sentenceCase(state);
const sentenceCase = (state: string) => { const text = state.replace(/_/g, " "); return text.charAt(0).toUpperCase() + text.slice(1); };
const backupStatusLabel = (status: string) => ({ never: t`Never run`, pending: t`Waiting to start`, running: t`Running`, promoting: t`Finishing`,
  available: t`Succeeded`, failed: t`Failed`, expired: t`Expired by retention`,
  deployment_backup_requires_host_supervisor: t`Run by whoever runs your server` } as Record<string, string>)[status] ?? sentenceCase(status);

const failedDeliveries = (count: number) => plural(count, { one: "# failed delivery", other: "# failed deliveries" });

// Tenant repair screens use control's separate platform session and authority.
const problemHref = (problem: Problem) => problem.makerspace_id === null
  ? consoleSessionHref(problem.fix_url, "platform")
  : `/control/makerspaces/makerspace/${problem.makerspace_id}/change/`;

export function PlatformDashboardPanel() {
  const dashboard = useQuery({ queryKey: ["platform-dashboard"], queryFn: getPlatformDashboard, refetchInterval: 60_000 });
  const problems = useQuery({ queryKey: ["platform-problems"], queryFn: getPlatformProblems, refetchInterval: 60_000 });
  const data = dashboard.data;
  const attention = problems.data?.results.find(problem => problem.status === "error");
  const refresh = () => { void dashboard.refetch(); void problems.refetch(); };
  // Problems has its own query: a failed dashboard must not hide the checks that explain it.
  const state = dashboard.isLoading && problems.isLoading ? adminQueryState(dashboard, "platform dashboard") : { status: "ready" as const };
  const callout: CalloutProps | undefined = dashboard.isError
    ? { size: "banner", tone: "danger", lead: t`Couldn't load the platform dashboard.`, body: dashboard.error.message, action: { label: t`Retry`, onClick: () => { void dashboard.refetch(); } } }
    : attention ? { size: "banner", tone: "danger", lead: attention.message, body: t`Review this check before your next deployment change.`, action: { label: t`Open in control panel`, href: problemHref(attention) } } : undefined;
  return <DashboardLayout header={{ title: t`Platform overview`, eyebrow: t`Space Works`,
    subtitle: t`Usage totals cover every live makerspace.`,
    meta: data ? <Trans>Checked <RelativeTime date={data.checked_at} /></Trans> : undefined,
    secondary: { label: t`Run checks now`, onClick: refresh, disabled: dashboard.isFetching || problems.isFetching, disabledReason: t`Checks are running.` } }}
    callout={callout}
    state={state} stats={data ? Object.entries(data.tenants_by_state).map(([name, value]) => ({ label: spaceStateStatLabel(name), value })) : []}
    overflowStats={data ? { label: t`Delivery and usage totals`, stats: [
      { label: t`Failed emails`, value: data.failed_deliveries.email },
      { label: t`Failed notifications`, value: data.failed_deliveries.notifications },
      ...Object.entries(data.usage_totals).map(([key, value]) => ({ label: limitLabel(key), value: usageAmount(value, key === "storage" ? "bytes" : "count") })),
    ] } : undefined}
    main={[
      { title: t`Problems`, empty: { message: t`All checks passed. Run checks again after a deployment change.` },
        content: problems.isLoading ? <p role="status">{t`Running checks…`}</p> : problems.isError ? <EmptyState message={t`Couldn't load problems. Try again.`} action={{ label: t`Retry`, onClick: () => { void problems.refetch(); } }} />
          : <div className="grid gap-3"><p className="text-sm text-muted">{problems.data ? <Trans>Checked <RelativeTime date={problems.data.checked_at} />.</Trans> : null}{" "}{t`Checks also run every 15 minutes through the platform scheduler.`}</p>
            {problems.data?.results.map((row, index) => <ListRow key={`${row.key}:${row.makerspace_id}:${index}`} title={row.message}
              meta={<StatusPill tone={row.status === "error" ? "danger" : row.status === "warn" ? "warn" : "success"} label={row.status === "ok" ? t`OK` : row.status === "warn" ? t`Warning` : t`Error`} />}
              right={<a className="desk-button" href={problemHref(row)}>{t`Open in control panel`}</a>} />)}</div>,
        isEmpty: Boolean(problems.data && !problems.data.results.length) },
      // Decision 242(l): counts by space and a platform-wide finder; superadmin-only routes, never rows.
      { title: t`Queues and safety by space`, content: <PlatformQueuesTable />, empty: { message: t`No live spaces yet.` } },
      { title: t`Find across spaces`, content: <PlatformSearch spaceNames={Object.fromEntries((data?.tenants ?? []).map(tenant => [tenant.id, tenant.name]))} />,
        empty: { message: t`Search is unavailable.` } },
      { title: t`Analytics`, content: <PlatformAnalyticsPanels spaces={data?.tenants} />, empty: { message: t`No platform activity yet.` } },
      ...(data ? [
        { title: t`Makerspace usage`, empty: { message: t`No usage yet. Check again after a space is active.` }, isEmpty: !data.tenants.length,
          content: <div className="grid gap-3">{data.tenants.map(tenant => <details key={tenant.id} className="rounded-xl border border-line bg-panel p-4">
            <summary className="min-h-11 cursor-pointer rounded-control py-2 font-display text-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{tenant.name}</summary>
            <UsageTable data={tenant.usage} />
          </details>)}</div> },
        { title: t`Background jobs`, empty: { message: t`No background job records yet. Ask whoever runs your server to check the background services.` }, isEmpty: !data.scheduler.length,
          content: <section id="scheduler"><p className="mb-4 text-sm text-muted">{t`These jobs send reminders, run backups and expire holds. If one is late, ask whoever runs your server to check that the background services are running.`}</p>
            <DataTable data={data.scheduler} getRowId={row => row.name} columns={[
              { key: "name", header: t`Task` }, { key: "cadence_minutes", header: t`Cadence`, render: row => plural(row.cadence_minutes, { one: "Every # minute", other: "Every # minutes" }) },
              { key: "last_run_at", header: t`Last execution`, render: row => row.last_run_at ? <RelativeTime date={row.last_run_at} /> : t`No execution recorded` },
              { key: "status", header: t`Status`, render: row => <StatusPill label={row.status === "ok" ? t`OK` : row.status === "warn" ? t`Warning` : t`Error`} tone={row.status === "ok" ? "success" : row.status === "warn" ? "warn" : "danger"} /> },
            ]} /></section> },
      ] : []),
    ]}
    railContent={data ? <section aria-label={t`Backup and offsite`} className="grid gap-3"><KeyValueCard title={t`Backup status`} items={[
            { label: t`Last backup result`, value: <StatusPill label={data.backup.status_label || backupStatusLabel(data.backup.status)} /> },
            { label: t`Last success`, value: data.backup.last_success_at ? <RelativeTime date={data.backup.last_success_at} /> : t`No execution recorded` },
            { label: t`Automatic backups`, value: <StatusPill label={data.backup.automatic_enabled ? t`On` : t`Off`} tone={data.backup.automatic_enabled ? "success" : "neutral"} /> },
            ...data.offsite.map(row => ({ label: row.name, value: <><StatusPill label={offsiteStateLabel(row.state)} tone={row.has_error ? "warn" : "neutral"} />{row.has_error ? t` · Needs attention` : ""} … {row.verified_at ? <RelativeTime date={row.verified_at} /> : t`No verification recorded`}</> })),
            ...(!data.offsite.length ? [{ label: t`Offsite destinations`, value: t`No offsite destinations configured.` }] : []),
          ]} /><a className="desk-button" href={consoleSessionHref("/admin/platform-data", "platform")}>{t`Backup settings`}</a></section> : undefined}
    rail={data ? { title: t`Delivery`, items: [
      { key: "emails", actor: t`Email`, children: failedDeliveries(data.failed_deliveries.email), date: data.checked_at },
      { key: "notifications", actor: t`Notifications`, children: failedDeliveries(data.failed_deliveries.notifications), date: data.checked_at },
    ], seeAll: { label: t`Platform settings`, href: consoleSessionHref("/admin/platform", "platform") } } : undefined} />;
}

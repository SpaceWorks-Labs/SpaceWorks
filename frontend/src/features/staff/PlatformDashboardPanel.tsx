import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { DashboardLayout } from "../../components/layouts";
import { type CalloutProps, DataTable, EmptyState, KeyValueCard, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { adminQueryState } from "./adminPresentation";
import { getPlatformDashboard, getPlatformProblems, usageAmount, type Problem } from "./platformMonitoringApi";
import { UsageTable } from "./TenantUsagePanel";
import { PlatformAnalyticsPanels } from "./PlatformAnalyticsPanels";

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
    ? { size: "banner", tone: "danger", lead: "Couldn't load the platform dashboard.", body: dashboard.error.message, action: { label: t`Retry`, onClick: () => { void dashboard.refetch(); } } }
    : attention ? { size: "banner", tone: "danger", lead: attention.message, body: t`Review this check before your next deployment change.`, action: { label: t`Inspect`, href: problemHref(attention) } } : undefined;
  return <DashboardLayout header={{ title: t`Platform`, eyebrow: t`Space Works`,
    subtitle: t`Usage totals cover every live, available tenant.`,
    meta: data ? <>{t`Checked `}<RelativeTime date={data.checked_at} /></> : undefined,
    secondary: { label: t`Run checks now`, onClick: refresh, disabled: dashboard.isFetching || problems.isFetching, disabledReason: "Checks are running." } }}
    callout={callout}
    state={state} stats={data ? Object.entries(data.tenants_by_state).map(([name, value]) => ({ label: `${name.replace(/_/g, " ")} tenants`, value })) : []}
    overflowStats={data ? { label: t`Delivery and usage totals`, stats: [
      { label: t`Failed emails`, value: data.failed_deliveries.email },
      { label: t`Failed notifications`, value: data.failed_deliveries.notifications },
      ...Object.entries(data.usage_totals).map(([key, value]) => ({ label: key.replace(/_/g, " "), value: usageAmount(value, key === "storage" ? "bytes" : "count") })),
    ] } : undefined}
    main={[
      { title: t`Analytics`, content: <PlatformAnalyticsPanels spaces={data?.tenants} />, empty: { message: t`No platform activity yet.` } },
      { title: t`Problems`, empty: { message: t`All checks passed. Run checks again after a deployment change.` },
        content: problems.isLoading ? <p role="status">{t`Running checks…`}</p> : problems.isError ? <EmptyState message={t`Couldn't load problems. Try again.`} action={{ label: t`Retry`, onClick: () => { void problems.refetch(); } }} />
          : <div className="grid gap-3"><p className="text-sm text-muted">{problems.data ? <>{t`Checked `}<RelativeTime date={problems.data.checked_at} />. </> : null}{t`Checks also run every 15 minutes through the platform scheduler.`}</p>
            {problems.data?.results.map((row, index) => <ListRow key={`${row.key}:${row.makerspace_id}:${index}`} title={row.message}
              meta={<StatusPill tone={row.status === "error" ? "danger" : row.status === "warn" ? "warn" : "success"} label={row.status === "ok" ? t`OK` : row.status === "warn" ? t`Warning` : t`Error`} />}
              right={<a className="desk-button" href={problemHref(row)}>{t`Inspect`}</a>} />)}</div>,
        isEmpty: Boolean(problems.data && !problems.data.results.length) },
      ...(data ? [
        { title: t`Tenant usage`, empty: { message: t`No tenant usage yet. Check again after a space is active.` }, isEmpty: !data.tenants.length,
          content: <div className="grid gap-3">{data.tenants.map(tenant => <details key={tenant.id} className="rounded-xl border border-line bg-panel p-4">
            <summary className="min-h-11 cursor-pointer rounded-control py-2 font-display text-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{tenant.name}</summary>
            <UsageTable data={tenant.usage} />
          </details>)}</div> },
        { title: t`Scheduler freshness`, empty: { message: t`No scheduler records yet. Check the scheduled runner.` }, isEmpty: !data.scheduler.length,
          content: <section id="scheduler"><p className="mb-4 text-sm text-muted">{t`For missing executions, check the host's beat and worker services, or its scheduled cron runner. For failed executions, inspect worker logs. Freshness records show beat completions and cron attempts.`}</p>
            <DataTable data={data.scheduler} getRowId={row => row.name} columns={[
              { key: "name", header: "Task" }, { key: "cadence_minutes", header: "Cadence", render: row => `${row.cadence_minutes} minutes` },
              { key: "last_run_at", header: "Last execution", render: row => row.last_run_at ? <RelativeTime date={row.last_run_at} /> : "No execution recorded" },
              { key: "status", header: "Status", render: row => <StatusPill label={row.status === "ok" ? t`OK` : row.status === "warn" ? t`Warning` : t`Error`} tone={row.status === "ok" ? "success" : row.status === "warn" ? "warn" : "danger"} /> },
            ]} /></section> },
      ] : []),
    ]}
    railContent={data ? <section aria-label={t`Backup and offsite`} className="grid gap-3"><KeyValueCard title={t`Backup status`} items={[
            { label: t`Last backup result`, value: <StatusPill label={data.backup.status} /> },
            { label: t`Last success`, value: data.backup.last_success_at ? <RelativeTime date={data.backup.last_success_at} /> : "No execution recorded" },
            { label: t`Automatic backups`, value: <StatusPill label={data.backup.automatic_enabled ? t`On` : t`Off`} tone={data.backup.automatic_enabled ? "success" : "neutral"} /> },
            ...data.offsite.map(row => ({ label: row.name, value: <><StatusPill label={row.state.replace(/_/g, " ")} tone={row.has_error ? "warn" : "neutral"} />{row.has_error ? t` · Needs attention` : ""} … {row.verified_at ? <RelativeTime date={row.verified_at} /> : t`No verification recorded`}</> })),
            ...(!data.offsite.length ? [{ label: t`Offsite destinations`, value: "No offsite destinations configured." }] : []),
          ]} /><a className="desk-button" href={consoleSessionHref("/admin/backup-restore", "platform")}>{t`Backup settings`}</a></section> : undefined}
    rail={data ? { title: t`Delivery`, items: [
      { key: "emails", actor: "Email", children: `${data.failed_deliveries.email} failed deliveries`, date: data.checked_at },
      { key: "notifications", actor: "Notifications", children: `${data.failed_deliveries.notifications} failed deliveries`, date: data.checked_at },
    ], seeAll: { label: t`Platform settings`, href: consoleSessionHref("/admin/platform", "platform") } } : undefined} />;
}

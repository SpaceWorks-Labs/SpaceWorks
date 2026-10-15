import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "../../components/layouts";
import { DataTable, EmptyState, KeyValueCard, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { adminQueryState } from "./adminPresentation";
import { getPlatformDashboard, getPlatformProblems, usageAmount } from "./platformMonitoringApi";
import { UsageTable } from "./TenantUsagePanel";

export function PlatformDashboardPanel() {
  const dashboard = useQuery({ queryKey: ["platform-dashboard"], queryFn: getPlatformDashboard, refetchInterval: 60_000 });
  const problems = useQuery({ queryKey: ["platform-problems"], queryFn: getPlatformProblems, refetchInterval: 60_000 });
  const data = dashboard.data;
  const attention = problems.data?.results.find(problem => problem.status === "error");
  const refresh = () => { void dashboard.refetch(); void problems.refetch(); };
  const state = adminQueryState(dashboard, "platform dashboard");
  return <DashboardLayout header={{ title: "Platform", eyebrow: "Space Works",
    subtitle: "Hidden tenants are excluded. Usage totals cover live, available tenants.",
    meta: data ? <>Checked <RelativeTime date={data.checked_at} /></> : undefined,
    secondary: { label: "Run checks now", onClick: refresh, disabled: dashboard.isFetching || problems.isFetching, disabledReason: "Checks are running." } }}
    callout={attention ? { size: "banner", tone: "danger", lead: attention.message, body: "Review this check before your next deployment change.", action: { label: "Inspect", href: attention.fix_url } } : undefined}
    state={state} stats={data ? Object.entries(data.tenants_by_state).map(([name, value]) => ({ label: `${name.replace(/_/g, " ")} tenants`, value })) : []}
    overflowStats={data ? { label: "Delivery and usage totals", stats: [
      { label: "Failed emails", value: data.failed_deliveries.email },
      { label: "Failed notifications", value: data.failed_deliveries.notifications },
      ...Object.entries(data.usage_totals).map(([key, value]) => ({ label: key.replace(/_/g, " "), value: usageAmount(value, key === "storage" ? "bytes" : "count") })),
    ] } : undefined}
    main={[
      { title: "Problems", empty: { message: "All checks passed. Run checks again after a deployment change." },
        content: problems.isLoading ? <p role="status">Running checks…</p> : problems.isError ? <EmptyState message="Couldn't load problems. Try again." action={{ label: "Retry", onClick: () => { void problems.refetch(); } }} />
          : <div className="grid gap-3"><p className="text-sm text-muted">Checks also run every 15 minutes through the platform scheduler.</p>
            {problems.data?.results.map((row, index) => <ListRow key={`${row.key}:${row.makerspace_id}:${index}`} title={row.message}
              meta={<StatusPill tone={row.status === "error" ? "danger" : row.status === "warn" ? "warn" : "success"} label={row.status === "ok" ? "OK" : row.status === "warn" ? "Warning" : "Error"} />}
              right={<a className="desk-button" href={row.fix_url}>Inspect</a>} />)}</div>,
        isEmpty: Boolean(problems.data && !problems.data.results.length) },
      ...(data ? [
        { title: "Tenant usage", empty: { message: "No tenant usage yet. Check again after a space is active." }, isEmpty: !data.tenants.length,
          content: <div className="grid gap-3">{data.tenants.map(tenant => <details key={tenant.id} className="rounded-xl border border-line bg-panel p-4">
            <summary className="min-h-11 cursor-pointer rounded-control py-2 font-display text-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{tenant.name}</summary>
            <a className="desk-button mb-4" href={`/m/${tenant.slug}/admin/usage`}>Open usage page</a><UsageTable data={tenant.usage} />
          </details>)}</div> },
        { title: "Scheduler freshness", empty: { message: "No scheduler records yet. Check the scheduled runner." }, isEmpty: !data.scheduler.length,
          content: <section id="scheduler"><p className="mb-4 text-sm text-muted">For missing executions, check the host's beat and worker services, or its scheduled cron runner. For failed executions, inspect worker logs. Freshness records show beat completions and cron attempts.</p>
            <DataTable data={data.scheduler} getRowId={row => row.name} columns={[
              { key: "name", header: "Task" }, { key: "cadence_minutes", header: "Cadence", render: row => `${row.cadence_minutes} minutes` },
              { key: "last_run_at", header: "Last execution", render: row => row.last_run_at ? <RelativeTime date={row.last_run_at} /> : "No execution recorded" },
              { key: "status", header: "Status", render: row => <StatusPill label={row.status === "ok" ? "OK" : row.status === "warn" ? "Warning" : "Error"} tone={row.status === "ok" ? "success" : row.status === "warn" ? "warn" : "danger"} /> },
            ]} /></section> },
        { title: "Backup and offsite", empty: { message: "No backup status yet. Open backup settings to create an archive." },
          content: <KeyValueCard title="Backup status" items={[
            { label: "Last backup result", value: <StatusPill label={data.backup.status} /> },
            { label: "Last success", value: data.backup.last_success_at ? <RelativeTime date={data.backup.last_success_at} /> : "No execution recorded" },
            { label: "Automatic backups", value: <StatusPill label={data.backup.automatic_enabled ? "On" : "Off"} tone={data.backup.automatic_enabled ? "success" : "neutral"} /> },
            ...data.offsite.map(row => ({ label: row.name, value: <><StatusPill label={row.state.replace(/_/g, " ")} tone={row.has_error ? "warn" : "neutral"} />{row.has_error ? " · Needs attention" : ""} … {row.verified_at ? <RelativeTime date={row.verified_at} /> : "No verification recorded"}</> })),
            ...(!data.offsite.length ? [{ label: "Offsite destinations", value: "No offsite destinations configured." }] : []),
          ]} />,
          action: { label: "Backup settings", href: "/admin/backup-restore" } },
      ] : []),
    ]}
    rail={data ? { title: "Delivery", items: [
      { key: "emails", actor: "Email", children: `${data.failed_deliveries.email} failed deliveries`, date: data.checked_at },
      { key: "notifications", actor: "Notifications", children: `${data.failed_deliveries.notifications} failed deliveries`, date: data.checked_at },
    ], seeAll: { label: "Platform settings", href: "/admin/platform" } } : undefined} />;
}

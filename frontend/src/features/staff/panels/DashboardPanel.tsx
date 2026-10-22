import type { ReactNode } from "react";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { DashboardLayout, type DashboardLayoutProps } from "../../../components/layouts/DashboardLayout";
import { useStaffGet, type Makerspace } from "./shared";
import { dashboardDestination, dashboardHref } from "./dashboardLinks";
import { filterTabsByEnabledModules } from "../staffTabs";
import { DashboardActivity, DashboardDueBack } from "./DashboardWidgets";
import { DashboardQuickAdd } from "./DashboardQuickAdd";
import { DashboardArchiveStatus } from "./DashboardArchiveStatus";
import { MACHINE_TILE_KEYS, TILES, type DashboardCounts } from "./DashboardStats";
import { DashboardAnalyticsWidgets, HandoverQueueHome } from "./DashboardAnalyticsWidgets";
import type { DashboardAnalytics } from "./analyticsApi";
import { staffTabPath } from "../staffTabs";

type Props = {
  makerspace: Makerspace; canManageMakerspace: boolean; allowedTabs?: readonly string[];
  actions?: readonly string[]; isSuperadmin?: boolean; singleTenantLocked?: boolean;
  guestOnly?: boolean; progress?: ReactNode;
};

export function DashboardPanel({ makerspace, canManageMakerspace, allowedTabs, actions,
  isSuperadmin = false, singleTenantLocked = false, guestOnly = false, progress }: Props) {
  const dashboard = useStaffGet<DashboardCounts & DashboardAnalytics>(["dashboard", makerspace.id], `/admin/makerspace/${makerspace.id}/dashboard`);
  if (dashboard.isSuccess && dashboard.data.scope_mode === "handover") return <HandoverQueueHome queues={dashboard.data.queue_tiles}
    slug={makerspace.slug} singleTenantLocked={singleTenantLocked} guestOnly={guestOnly} />;
  const permitted = TILES.filter(tile => (
    (dashboard.data?.scope_mode !== "machine" || MACHINE_TILE_KEYS.has(tile.key))
    && filterTabsByEnabledModules([dashboardDestination(tile.key).tab], makerspace).length > 0
    && (tile.key !== "failed_emails" || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("email"))
    // The server returns pending_payments only to finance staff (manage_makerspace or view_finance).
    // A payments-tab holder without that (an Event Manager settling registrations) would see a false 0.
    && (tile.key !== "pending_payments" || (dashboard.data !== undefined && "pending_payments" in dashboard.data))
    && (!allowedTabs || allowedTabs.includes(dashboardDestination(tile.key).tab))
    && (!tile.key.includes("prints") || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("printing"))
    && (tile.key !== "maintenance_overdue" || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("maintenance"))
  ));
  const priority = (tile: typeof permitted[number]) => tile.actionNeeded && (dashboard.data?.[tile.key] ?? 0) > 0
    ? tile.tone === "danger" ? 0 : 1 : 2;
  const ranked = [...permitted].sort((a, b) => priority(a) - priority(b));
  const href = (key: string) => dashboardHref(key, makerspace.slug, singleTenantLocked, guestOnly);
  const alert = ["overdue_loans", "failed_emails", "open_problem_reports", "maintenance_overdue"]
    .map(key => permitted.find(tile => tile.key === key && (dashboard.data?.[tile.key] ?? 0) > 0)).find(Boolean);
  const count = alert ? dashboard.data?.[alert.key] ?? 0 : 0;
  const alertLead: Record<string, string> = {
    overdue_loans: `${count} loan${count === 1 ? " is" : "s are"} overdue.`,
    failed_emails: `${count} email${count === 1 ? "" : "s"} could not be delivered.`,
    open_problem_reports: `${count} problem report${count === 1 ? " needs" : "s need"} review.`,
    maintenance_overdue: `${count} maintenance task${count === 1 ? " is" : "s are"} overdue.`,
  };
  // Widgets need explicit actor authority as well as the already-filtered tab list.
  const widgetsReady = allowedTabs !== undefined && actions !== undefined && dashboard.isSuccess;
  const routing = { makerspace, guestOnly, singleTenantLocked };
  // BK-17: a Space Manager sees their own archive status; the custody read needs manage_makerspace.
  const archiveStatus = (canManageMakerspace || isSuperadmin) && !guestOnly
    && (makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("backup"))
    && filterTabsByEnabledModules(["backups"], makerspace).length > 0 && (!allowedTabs || allowedTabs.includes("backups"))
    ? <DashboardArchiveStatus makerspaceId={makerspace.id} slug={makerspace.slug} guestOnly={guestOnly} singleTenantLocked={singleTenantLocked} />
    : undefined;
  const layout = (rail?: DashboardLayoutProps["rail"], main: DashboardLayoutProps["main"] = []) => (
    <DashboardQuickAdd {...routing} actions={actions} allowedTabs={allowedTabs} isSuperadmin={isSuperadmin}>
      {primary => <DashboardLayout
        header={{ title: "Dashboard", eyebrow: new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" }),
          subtitle: `What's happening at ${makerspace.name}.`, primary }}
        state={{ status: dashboard.isLoading ? "loading" : dashboard.error ? "error" : "ready",
          error: "Couldn't load dashboard. Try again.", onRetry: () => { void dashboard.refetch(); } }}
        progress={progress}
        stats={ranked.map(tile => ({ label: tile.label, value: dashboard.data?.[tile.key] ?? 0,
          // Overdue, problems, out of stock, failed email and overdue maintenance keep their danger signal.
          tone: tile.actionNeeded && (dashboard.data?.[tile.key] ?? 0) > 0 ? tile.tone === "danger" ? "danger" : "attention" : "neutral",
          href: href(tile.key) }))}
        callout={alert ? { size: "banner", tone: "warn", lead: alertLead[alert.key],
          action: { label: "Review", href: href(alert.key) } } : undefined}
        main={[...main, ...(dashboard.data?.widgets ? [{ title: "Analytics", empty: { message: "No analytics widgets available." },
          content: <DashboardAnalyticsWidgets widgets={dashboard.data.widgets.filter(widget => widget.required_modules.every(module =>
            makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes(module)))} makerspaceId={makerspace.id}
            reportsHref={consoleSessionHref(staffTabPath("reports", guestOnly, makerspace.slug, singleTenantLocked))} /> }] : [])]} rail={rail}
        railContent={archiveStatus}
      />}
    </DashboardQuickAdd>
  );
  const withDueBack = (rail?: DashboardLayoutProps["rail"], activitySections: DashboardLayoutProps["main"] = []) => widgetsReady && allowedTabs.includes("requests")
    && filterTabsByEnabledModules(["requests"], makerspace).length > 0 && (isSuperadmin || actions.includes("issue_request"))
    ? <DashboardDueBack {...routing}>{main => layout(rail, [...main, ...activitySections])}</DashboardDueBack> : layout(rail, activitySections);
  return widgetsReady && allowedTabs.includes("audit")
    ? <DashboardActivity {...routing}>{withDueBack}</DashboardActivity> : withDueBack();
}

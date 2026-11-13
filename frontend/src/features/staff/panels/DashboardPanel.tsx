import { formatLocale } from "../../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { NextUpEvents, type NextUpEvent } from "../eventProgramme/NextUpEvents";
import type { ReactNode } from "react";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { DashboardLayout, type DashboardLayoutProps } from "../../../components/layouts/DashboardLayout";
import { useStaffGet, type Makerspace } from "./shared";
import { dashboardDestination, dashboardHref } from "./dashboardLinks";
import { filterTabsByEnabledModules } from "../staffTabs";
import { capabilityOn } from "../../../lib/features";
import { DashboardActivity, DashboardDueBack } from "./DashboardWidgets";
import { DashboardQuickAdd } from "./DashboardQuickAdd";
import { DashboardArchiveStatus } from "./DashboardArchiveStatus";
import { LateShiftLine } from "../../../components/delight/SneakyLines";
import { MACHINE_TILE_KEYS, TILES, type DashboardCounts } from "./DashboardStats";
import { DashboardAnalyticsWidgets, HandoverQueueHome } from "./DashboardAnalyticsWidgets";
import type { DashboardAnalytics } from "./analyticsApi";
import { staffTabPath } from "../staffTabs";
import { WaitingOnMe } from "./dashboardAreas/WaitingOnMe";
import { AreaSections } from "./dashboardAreas/AreaSections";
import type { Attention } from "./dashboardAreas/attention";
import { DashboardFailedAreas } from "./DashboardFailedAreas";

const NEW_242_TILES = new Set<string>(["due_today_loans", "due_soon_loans", "true_low_stock", "in_repair", "payments_to_record",
  "today_events", "today_check_ins", "today_bookings", "room_outages_week"]);

type Props = {
  makerspace: Makerspace; canManageMakerspace: boolean; allowedTabs?: readonly string[];
  actions?: readonly string[]; isSuperadmin?: boolean; singleTenantLocked?: boolean;
  guestOnly?: boolean; progress?: ReactNode;
};

export function DashboardPanel({ makerspace, canManageMakerspace, allowedTabs, actions,
  isSuperadmin = false, singleTenantLocked = false, guestOnly = false, progress }: Props) {
  const dashboard = useStaffGet<DashboardCounts & DashboardAnalytics & { next_up_events?: NextUpEvent[]; attention?: Attention; failed_areas?: string[] }>(["dashboard", makerspace.id], `/admin/makerspace/${makerspace.id}/dashboard`);
  if (dashboard.isSuccess && dashboard.data.scope_mode === "handover") return <HandoverQueueHome queues={dashboard.data.queue_tiles}
    slug={makerspace.slug} singleTenantLocked={singleTenantLocked} guestOnly={guestOnly} />;
  const permitted = TILES.filter(tile => (
    (dashboard.data?.scope_mode !== "machine" || MACHINE_TILE_KEYS.has(tile.key))
    && filterTabsByEnabledModules([dashboardDestination(tile.key).tab], makerspace).length > 0
    && (tile.key !== "failed_emails" || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("email"))
    // The server returns pending_payments only to finance staff (manage_makerspace or view_finance).
    // A payments-tab holder without that (an Event Manager settling registrations) would see a false 0.
    && (tile.key !== "pending_payments" || (dashboard.data !== undefined && "pending_payments" in dashboard.data))
    // Decision 242 counters: shown only when the server sent them (a missing field is not a 0).
    && (!NEW_242_TILES.has(tile.key) || (dashboard.data !== undefined && tile.key in dashboard.data))
    && (!allowedTabs || allowedTabs.includes(dashboardDestination(tile.key).tab))
    && (!tile.key.includes("prints") || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("machine_service"))
    // The problem-report list (needsfix → Problem reports) is served only with the reports module.
    && (tile.key !== "open_problem_reports" || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("reports"))
    && (tile.key !== "maintenance_overdue" || makerspace.enabled_features === undefined || capabilityOn(makerspace, "machines.maintenance"))
    && (tile.key !== "room_outages_week" || makerspace.enabled_features === undefined || capabilityOn(makerspace, "bookings.room_maintenance"))
  ));
  // The generated Dashboard type also carries list fields (failed_areas); a tile key is only ever a count.
  const counter = (key: string): number => {
    const value = (dashboard.data as Record<string, unknown> | undefined)?.[key];
    return typeof value === "number" ? value : 0;
  };
  const priority = (tile: typeof permitted[number]) => tile.actionNeeded && (counter(tile.key)) > 0
    ? tile.tone === "danger" ? 0 : 1 : 2;
  const ranked = [...permitted].sort((a, b) => priority(a) - priority(b));
  const href = (key: string) => dashboardHref(key, makerspace.slug, singleTenantLocked, guestOnly);
  const alert = ["overdue_loans", "failed_emails", "open_problem_reports", "maintenance_overdue"]
    .map(key => permitted.find(tile => tile.key === key && (counter(tile.key)) > 0)).find(Boolean);
  const count = alert ? counter(alert.key) : 0;
  const alertLead: Record<string, string> = {
    overdue_loans: plural(count, { one: "# loan is overdue.", other: "# loans are overdue." }),
    failed_emails: plural(count, { one: "# email could not be delivered.", other: "# emails could not be delivered." }),
    open_problem_reports: plural(count, { one: "# problem report needs review.", other: "# problem reports need review." }),
    maintenance_overdue: plural(count, { one: "# maintenance task is overdue.", other: "# maintenance tasks are overdue." }),
  };
  // Decision 242(j): with the per-area counters, "Waiting on me" and the area sections replace the
  // flat tile row; tiles the counters do not cover stay as compact numbers below them.
  const attention = dashboard.data?.attention;
  const covered = new Set(attention?.areas.flatMap(area => area.items.map(item => item.key)) ?? []);
  const attentionRouting = { slug: makerspace.slug, guestOnly, singleTenantLocked, allowedTabs };
  // Widgets need explicit actor authority as well as the already-filtered tab list.
  const widgetsReady = allowedTabs !== undefined && actions !== undefined && dashboard.isSuccess;
  const routing = { makerspace, guestOnly, singleTenantLocked };
  const stat = (tile: typeof ranked[number]) => ({ label: tile.label, value: counter(tile.key),
    // Overdue, problems, out of stock, failed email and overdue maintenance keep their danger signal.
    tone: tile.actionNeeded && (counter(tile.key)) > 0 ? tile.tone === "danger" ? "danger" as const : "attention" as const : "neutral" as const,
    href: href(tile.key) });
  // BK-17: a Space Manager sees their own backup status; the status read needs manage_makerspace.
  const archiveStatus = (canManageMakerspace || isSuperadmin) && !guestOnly
    && filterTabsByEnabledModules(["backups"], makerspace).length > 0 && (!allowedTabs || allowedTabs.includes("backups"))
    ? <DashboardArchiveStatus makerspaceId={makerspace.id} slug={makerspace.slug} guestOnly={guestOnly} singleTenantLocked={singleTenantLocked} />
    : undefined;
  const layout = (rail?: DashboardLayoutProps["rail"], main: DashboardLayoutProps["main"] = []) => (
    <DashboardQuickAdd {...routing} actions={actions} allowedTabs={allowedTabs} isSuperadmin={isSuperadmin}>
      {primary => <DashboardLayout
        header={{ title: t`Dashboard`, eyebrow: new Date().toLocaleDateString(formatLocale(), { weekday: "long", day: "numeric", month: "long" }),
          subtitle: t`What's happening at ${makerspace.name}.`, primary }}
        state={{ status: dashboard.isLoading ? "loading" : dashboard.error ? "error" : "ready",
          error: t`Couldn't load dashboard. Try again.`, onRetry: () => { void dashboard.refetch(); } }}
        progress={<><DashboardFailedAreas areas={dashboard.data?.failed_areas} onRetry={() => { void dashboard.refetch(); }} />{attention ? <WaitingOnMe attention={attention} routing={attentionRouting} onRetry={() => { void dashboard.refetch(); }} /> : null}
          <LateShiftLine />{progress}{dashboard.data?.next_up_events ? <NextUpEvents events={dashboard.data.next_up_events} /> : null}
          {attention ? <AreaSections attention={attention} routing={attentionRouting} /> : null}</>}
        stats={attention ? [] : ranked.map(stat)}
        overflowStats={attention ? { label: t`Other numbers`, stats: ranked.filter(tile => !covered.has(tile.key)).map(stat) } : undefined}
        callout={alert ? { size: "banner", tone: "warn", lead: alertLead[alert.key],
          action: { label: t`Review`, href: href(alert.key) } } : undefined}
        main={[...main, ...(dashboard.data?.widgets ? [{ title: t`Analytics`, empty: { message: t`No analytics widgets available.` },
          content: <DashboardAnalyticsWidgets widgets={dashboard.data.widgets.filter(widget => widget.required_modules.every(module =>
            makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes(module)))} makerspaceId={makerspace.id}
            reportsHref={allowedTabs?.includes("reports") ? consoleSessionHref(staffTabPath("reports", guestOnly, makerspace.slug, singleTenantLocked)) : undefined} /> }] : [])]} rail={rail}
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

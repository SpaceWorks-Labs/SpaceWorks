import { t } from "@lingui/core/macro";
import { StatCard } from "../../../components/ui";
import { DashboardLayout } from "../../../components/layouts";
import { AnalyticsData } from "./AnalyticsData";
import { analyticsMeta, analyticsRows, useAnalyticsReport, type DashboardAnalytics, type DashboardWidget } from "./analyticsApi";
import { DataState } from "./OperationsReportState";
import { staffTabPath } from "../staffTabs";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { wireChartSpec } from "./charts/wireChartSpec";
import type { ChartRecord } from "./charts/chartSpec";

export function DashboardAnalyticsWidgets({ widgets, reportsHref, makerspaceId, analyticsBase }: {
  widgets: DashboardWidget[]; reportsHref?: string; makerspaceId: number; analyticsBase?: string;
}) {
  if (!widgets.length) return <p className="text-sm text-muted">{t`No analytics widgets are available for your enabled modules and actions.`}</p>;
  return <div className="grid min-w-0 gap-6">{widgets.map(widget => <AnalyticsWidget key={widget.key}
    widget={widget} reportsHref={reportsHref} makerspaceId={makerspaceId} analyticsBase={analyticsBase} />)}</div>;
}

function AnalyticsWidget({ widget, reportsHref, makerspaceId, analyticsBase }: {
  widget: DashboardWidget; reportsHref?: string; makerspaceId: number; analyticsBase?: string;
}) {
  // Widget meta is a loose JSON object: deferred widgets carry their window, not rows.
  const widgetMeta = (analyticsMeta(widget.data) ?? {}) as Record<string, unknown>;
  const deferred = widgetMeta.deferred === true;
  const params = new URLSearchParams({ start: String(widgetMeta.start ?? ""),
    end: String(widgetMeta.end ?? ""), limit: "500" });
  const query = useAnalyticsReport(analyticsBase ?? `/admin/makerspace/${makerspaceId}/analytics`, widget.report_keys[0], params, deferred);
  const data = deferred ? query.data : widget.data;
  const rows: ChartRecord[] = analyticsRows(data).map(row => ({ makerspace_id: makerspaceId, ...row }));
  // Widgets carry their report spec but no chart_hint. Money uses separate lines.
  const hint = widget.kind === "heatmap" ? "heatmap" : widget.kind === "top_n" || widget.kind === "count" ? "bar"
    : ["machine-downtime", "machine-errors"].includes(widget.key) ? "stacked_bar"
      : widget.key === "event-funnel" ? "funnel" : undefined;
  const spec = widget.chart_spec ? wireChartSpec(widget.chart_spec, hint, rows) : undefined;
  return <section aria-label={widget.title} className="min-w-0 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">{widget.title}</h3>
    <p className="my-2 text-sm text-muted">{widget.kind === "queue" ? t`Operational queue` : widget.kind === "count" ? t`Current counts` : t`Last ${widget.default_period} calendar days`}</p>
    <DataState loading={deferred && query.isLoading} error={deferred ? query.error : undefined}
      onRetry={() => void query.refetch()} empty={false}>
      {widget.kind === "count" && spec ? <div className="grid gap-3 sm:grid-cols-2">{rows.flatMap((row, index) => spec.value_fields.map(field =>
        <StatCard key={`${index}:${field.field}`} label={`${String(row[spec.x.field] ?? "")} ${field.label ?? field.field}`} value={`${row[field.field] ?? "Unknown"} ${field.unit_field ? row[field.unit_field] ?? "" : field.unit}`} />))}</div> : null}
      <AnalyticsData title={widget.title} rows={rows} spec={spec} meta={analyticsMeta(data)} />
    </DataState>
    {reportsHref && widget.report_keys[0] ? <a className="desk-button mt-3" href={reportHref(reportsHref, widget.report_keys[0])}>{t`Open in reports`}</a> : null}
  </section>;
}

export function HandoverQueueHome({ queues, slug, singleTenantLocked = false, guestOnly = false }: {
  queues: DashboardAnalytics["queue_tiles"]; slug: string; singleTenantLocked?: boolean; guestOnly?: boolean;
}) {
  const destinations = [
    { key: "ready_to_issue" as const, label: t`Ready to issue`, tab: "requests", query: "queue=accepted" },
    { key: "due_returns" as const, label: t`Due returns`, tab: "requests", query: "queue=active&ordering=return_due_at" },
    { key: "pickups" as const, label: t`Pickups`, tab: "handover", query: "" },
  ];
  return <DashboardLayout header={{ title: t`Handover`, eyebrow: t`Physical handovers`, subtitle: t`Issue ready requests, receive returns and collect completed jobs.` }}
    state={{ status: "ready" }} stats={destinations.map(row => ({ label: row.label, value: queues?.[row.key] ?? 0,
      href: consoleSessionHref(`${staffTabPath(row.tab, guestOnly, slug, singleTenantLocked)}${row.query ? `?${row.query}` : ""}`) }))}
    main={[{ title: t`Your handover queues`, content: <p>{t`Choose a queue above to continue a physical handover.`}</p>, empty: { message: t`No handovers waiting.` } }]} />;
}

function reportHref(base: string, key: string) {
  const url = new URL(base, window.location.origin);
  url.searchParams.set("report", key);
  return url.pathname + url.search + url.hash;
}

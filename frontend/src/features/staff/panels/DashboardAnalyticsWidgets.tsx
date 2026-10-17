import { StatCard } from "../../../components/ui";
import { DashboardLayout } from "../../../components/layouts";
import { AnalyticsData } from "./AnalyticsData";
import { analyticsRows, type DashboardAnalytics, type DashboardWidget } from "./analyticsApi";
import { staffTabPath } from "../staffTabs";
import { wireChartSpec } from "./charts/wireChartSpec";
import type { ChartRecord } from "./charts/chartSpec";

export function DashboardAnalyticsWidgets({ widgets, reportsHref, makerspaceId }: {
  widgets: DashboardWidget[]; reportsHref: string; makerspaceId: number;
}) {
  if (!widgets.length) return <p className="text-sm text-muted">No analytics widgets are available for your enabled modules and actions.</p>;
  return <div className="grid min-w-0 gap-6">{widgets.map(widget => {
    const rows: ChartRecord[] = analyticsRows(widget.data).map(row => ({ makerspace_id: makerspaceId, ...row }));
    // Widgets carry their report spec but no chart_hint. Keep the registry's status/money/funnel presentations.
    const hint = widget.kind === "heatmap" ? "heatmap" : widget.kind === "top_n" || widget.kind === "count" ? "bar"
      : ["machine-downtime", "machine-errors", "revenue-over-time"].includes(widget.key) ? "stacked_bar"
        : widget.key === "event-funnel" ? "funnel" : undefined;
    const spec = widget.chart_spec ? wireChartSpec(widget.chart_spec, hint, rows) : undefined;
    return <section key={widget.key} aria-label={widget.title} className="min-w-0 rounded-xl border border-line bg-panel p-4">
      <h3 className="title-section">{widget.title}</h3>
      <p className="my-2 text-sm text-muted">{widget.kind === "queue" ? "Operational queue" : widget.kind === "count" ? "Current counts" : `Last ${widget.default_period} calendar days`}</p>
      {widget.kind === "count" && spec ? <div className="grid gap-3 sm:grid-cols-2">{rows.flatMap((row, index) => spec.value_fields.map(field =>
        <StatCard key={`${index}:${field.field}`} label={`${String(row[spec.x.field] ?? "")} ${field.label ?? field.field}`} value={`${row[field.field] ?? "Unknown"} ${field.unit_field ? row[field.unit_field] ?? "" : field.unit}`} />))}</div> : null}
      <AnalyticsData title={widget.title} rows={rows} spec={spec} meta={widget.data.meta} />
      {widget.report_keys[0] ? <a className="desk-button mt-3" href={`${reportsHref}?report=${encodeURIComponent(widget.report_keys[0])}`}>Open in reports</a> : null}
    </section>;
  })}</div>;
}

export function HandoverQueueHome({ queues, slug, singleTenantLocked = false, guestOnly = false }: {
  queues: DashboardAnalytics["queue_tiles"]; slug: string; singleTenantLocked?: boolean; guestOnly?: boolean;
}) {
  const destinations = [
    { key: "ready_to_issue" as const, label: "Ready to issue", tab: "requests", query: "queue=accepted" },
    { key: "due_returns" as const, label: "Due returns", tab: "requests", query: "queue=active&ordering=return_due_at" },
    { key: "pickups" as const, label: "Pickups", tab: "handover", query: "" },
  ];
  return <DashboardLayout header={{ title: "Handover", eyebrow: "Physical handovers", subtitle: "Issue ready requests, receive returns and collect completed jobs." }}
    state={{ status: "ready" }} stats={destinations.map(row => ({ label: row.label, value: queues?.[row.key] ?? 0,
      href: `${staffTabPath(row.tab, guestOnly, slug, singleTenantLocked)}${row.query ? `?${row.query}` : ""}` }))}
    main={[{ title: "Your handover queues", content: <p>Choose a queue above to continue a physical handover.</p>, empty: { message: "No handovers waiting." } }]} />;
}

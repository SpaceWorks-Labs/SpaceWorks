import { useState } from "react";
import { AnalyticsData } from "./panels/AnalyticsData";
import { AnalyticsPeriodControls } from "./panels/AnalyticsPeriodControls";
import { analyticsRows, type AnalyticsPeriod } from "./panels/analyticsApi";
import { DataState } from "./panels/OperationsReportState";
import { PLATFORM_CHART_SPECS, usePlatformAnalytics, type AnalyticsMakerspace } from "./platformAnalyticsApi";
import { PlatformAnalyticsPicker } from "./PlatformAnalyticsPicker";
import type { ChartRecord } from "./panels/charts/chartSpec";

/** Hidden buckets are counts only, with no tenant or outcome dimension, even in the table. */
export function platformChartRows(rows: ChartRecord[], spaces: AnalyticsMakerspace[] = []): ChartRecord[] {
  return rows.map(row => {
    if (row.bucket === "hidden_makerspaces") return { makerspace: "Hidden makerspaces", day: row.day,
      service: row.service, bucket: "Hidden makerspaces", count: row.count };
    const fields = ["period", "day", "service", "provider_source", "status", "bucket", "count", "currency", "amount",
      "metric", "entity_kind", "entity_id", "unit", "value"];
    return { makerspace: row.makerspace_id == null ? "Deployment" : spaces.find(space => space.id === row.makerspace_id)?.name ?? `Makerspace #${row.makerspace_id}`,
      ...Object.fromEntries(fields.filter(field => field in row).map(field => [field, row[field]])) };
  });
}

export function PlatformAnalyticsPanels() {
  const [period, setPeriod] = useState<AnalyticsPeriod>({ start: "", end: "", grain: "day" });
  return <div className="grid min-w-0 gap-6">
    <AnalyticsPeriodControls value={period} onChange={setPeriod} />
    <PlatformReport reportKey="platform-services" title="Platform services" period={period} />
    <PlatformReport reportKey="platform-usage" title="Platform usage" period={period} />
    <PlatformAnalyticsPicker period={period} />
  </div>;
}
function PlatformReport({ reportKey, title, period }: {
  reportKey: "platform-services" | "platform-usage"; title: string; period: AnalyticsPeriod;
}) {
  const query = usePlatformAnalytics(reportKey, period);
  const rows = platformChartRows(analyticsRows(query.data));
  const rawSpec = query.data?.chart_spec ?? PLATFORM_CHART_SPECS[reportKey];
  const spec = { ...rawSpec, series: rawSpec.series.map(field => field === "makerspace_id" ? "makerspace" : field) };
  return <section aria-label={title} className="min-w-0 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section mb-3">{title}</h3>
    <p className="mb-3 text-sm text-muted">{reportKey === "platform-services"
      ? "Platform service usage includes one anonymous Hidden makerspaces bucket per service and day. Own-provider counts include visible makerspaces only. Connect has no provider-attempt failure history."
      : "Business activity, module adoption, growth and app adoption exclude hidden makerspaces. Money and consumption stay separated by currency and unit."}</p>
    {query.isLoading ? <p role="status">Loading {title.toLowerCase()}…</p> : <DataState loading={false} error={query.error} empty={!rows.length} onRetry={() => void query.refetch()}>
      <AnalyticsData title={title} rows={rows} spec={spec}
        hint={query.data?.chart_hint ?? (reportKey === "platform-services" ? "stacked_bar" : "multi_line")} meta={query.data?.meta} />
    </DataState>}
  </section>;
}

import { t } from "@lingui/core/macro";
import { useState } from "react";
import { AnalyticsData } from "./panels/AnalyticsData";
import { AnalyticsPeriodControls } from "./panels/AnalyticsPeriodControls";
import { analyticsRows, type AnalyticsPeriod } from "./panels/analyticsApi";
import { DataState } from "./panels/OperationsReportState";
import { PLATFORM_CHART_SPECS, usePlatformAnalytics, type AnalyticsMakerspace } from "./platformAnalyticsApi";
import { PlatformAnalyticsPicker } from "./PlatformAnalyticsPicker";
import { PlatformSpaceComparison } from "./PlatformSpaceComparison";
import type { ChartRecord } from "./panels/charts/chartSpec";

/** Names each row's makerspace and keeps only the reported dimensions, never raw ids. */
export function platformChartRows(rows: ChartRecord[], spaces: AnalyticsMakerspace[] = []): ChartRecord[] {
  return rows.map(row => {
    const fields = ["period", "day", "service", "purpose", "provider_source", "status", "bucket", "count", "currency", "amount",
      "metric", "entity_kind", "entity_id", "unit", "value"];
    return { makerspace: row.makerspace_id == null ? "Deployment" : spaces.find(space => space.id === row.makerspace_id)?.name ?? `Makerspace #${row.makerspace_id}`,
      ...Object.fromEntries(fields.filter(field => field in row).map(field => [field, row[field]])) };
  });
}

export function PlatformAnalyticsPanels({ spaces }: { spaces?: AnalyticsMakerspace[] }) {
  const [period, setPeriod] = useState<AnalyticsPeriod>({ start: "", end: "", grain: "day" });
  return <div className="grid min-w-0 gap-6">
    <AnalyticsPeriodControls value={period} onChange={setPeriod} />
    <PlatformReport reportKey="platform-services" title={t`Platform services`} period={period} />
    <PlatformReport reportKey="platform-usage" title={t`Platform usage`} period={period} />
    <PlatformSpaceComparison period={period} spaces={spaces} />
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
      ? t`Platform service usage across every makerspace. Connect has no provider-attempt failure history.`
      : t`Business activity, module adoption, growth and app adoption across every makerspace. Money and consumption stay separated by currency and unit.`}</p>
    {query.isLoading ? <p role="status">{t`Loading ${title.toLowerCase()}…`}</p> : <DataState loading={false} error={query.error} empty={!rows.length} onRetry={() => void query.refetch()}>
      <AnalyticsData title={title} rows={rows} spec={spec}
        hint={reportKey === "platform-services" ? "stacked_bar" : "multi_line"} meta={query.data?.meta} />
    </DataState>}
  </section>;
}

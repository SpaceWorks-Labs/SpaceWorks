import { analyticsRows, periodParams, useAnalyticsReport, type AnalyticsPeriod } from "./analyticsApi";
import { AnalyticsData } from "./AnalyticsData";
import { DataState } from "./OperationsReportState";
import type { ReportCatalogItem } from "./operationsReportsConfig";
import { reportAreaGroups } from "./reportAreas";
import { StructuredApiError } from "../../../lib/api";

export function ReportChartResult({ report, base, period, filters = {}, makerspaceId }: {
  report: ReportCatalogItem; base: string; period: AnalyticsPeriod; filters?: Record<string, string>;
  makerspaceId?: number;
}) {
  const params = periodParams(period, report.grains);
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const enabled = report.available !== false && report.previewable !== false;
  const query = useAnalyticsReport(base, report.key, params, enabled);
  if (!enabled) return <p className="text-sm text-muted">{report.unavailable_reason || "This report is available through exports only."}</p>;
  if (query.isLoading) return <p role="status" className="text-sm text-muted">Loading {report.title}…</p>;
  if (query.error instanceof StructuredApiError && query.error.status === 403) return <p role="alert" className="text-danger">Access to this makerspace's analytics is blocked. Your account needs authority for this report in this space.</p>;
  const rows = analyticsRows(query.data).map(row => makerspaceId !== undefined ? { makerspace_id: makerspaceId, ...row } : row);
  return <DataState loading={false} error={query.error} empty={!rows.length} onRetry={() => void query.refetch()}>
    <button type="button" className="desk-button mb-3" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh report</button>
    <AnalyticsData title={report.title} rows={rows} spec={report.chart_spec} hint={report.chart_hint} meta={query.data?.meta} />
  </DataState>;
}

/** Only the expanded report fetches. The catalog, including identity-bearing keys, owns visibility. */
export function ReportAreaSections({ reports, selected, onSelect, base, period, filters, makerspaceId }: {
  reports: ReportCatalogItem[]; selected: string; onSelect: (key: string) => void; base: string;
  period: AnalyticsPeriod; filters?: Record<string, string>; makerspaceId?: number;
}) {
  return <div className="space-y-6">{reportAreaGroups(reports).map(([area, entries]) => <section key={area} aria-label={area}>
    <h2 className="title-panel mb-3">{area}</h2>
    <div className="space-y-3">{entries.map(report => <section key={report.key}
      className="rounded-xl border border-line bg-panel p-4">
      <button type="button" aria-expanded={selected === report.key} onClick={() => onSelect(selected === report.key ? "" : report.key)}
        className="min-h-11 w-full rounded-control py-2 text-left font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        {report.title}{report.identity_bearing ? <span className="ml-2 text-sm text-muted">Contains personal data</span> : null}
      </button>
      {selected === report.key ? <ReportChartResult report={report} base={base} period={period} filters={filters} makerspaceId={makerspaceId} /> : null}
    </section>)}</div>
  </section>)}</div>;
}

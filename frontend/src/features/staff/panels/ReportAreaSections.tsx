import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { analyticsRows, analyticsMeta, periodParams, useAnalyticsReport, type AnalyticsPeriod } from "./analyticsApi";
import { AnalyticsData } from "./AnalyticsData";
import { DataState } from "./OperationsReportState";
import type { ReportCatalogItem } from "./operationsReportsConfig";
import { groupReports } from "./reportGroups";
import { ReportPinButton } from "./ReportPinButton";
import { StructuredApiError } from "../../../lib/api";

export function ReportChartResult({ report, base, period, filters = {}, makerspaceId }: {
  report: ReportCatalogItem; base: string; period: AnalyticsPeriod; filters?: Record<string, string>;
  makerspaceId?: number;
}) {
  const params = periodParams(period, report.grains);
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const enabled = report.available !== false && report.previewable !== false;
  const query = useAnalyticsReport(base, report.key, params, enabled);
  if (!enabled) return <p className="text-sm text-muted">{report.unavailable_reason || t`This report is available through exports only.`}</p>;
  if (query.isLoading) return <LogoLoader label={t`Loading ${report.title}…`} size={48} className="min-h-16 py-3" />;
  if (query.error instanceof StructuredApiError && query.error.status === 403) return <p role="alert" className="text-danger">{t`Access to this makerspace's analytics is blocked. Your account needs authority for this report in this space.`}</p>;
  const rows = analyticsRows(query.data).map(row => makerspaceId !== undefined ? { makerspace_id: makerspaceId, ...row } : row);
  return <DataState loading={false} error={query.error} empty={!rows.length} onRetry={() => void query.refetch()}>
    <button type="button" className="desk-button mb-3" disabled={query.isFetching} onClick={() => void query.refetch()}>{t`Refresh report`}</button>
    <AnalyticsData title={report.title} rows={rows} spec={report.chart_spec} hint={report.chart_hint} meta={analyticsMeta(query.data)} />
  </DataState>;
}

/** Only the expanded report fetches. The catalog, including identity-bearing keys, owns visibility. */
const NO_PINS: ReadonlySet<string> = new Set();

export function ReportAreaSections({ reports, selected, onSelect, base, period, filters, makerspaceId, pinned = NO_PINS, onTogglePin }: {
  reports: ReportCatalogItem[]; selected: string; onSelect: (key: string) => void; base: string;
  period: AnalyticsPeriod; filters?: Record<string, string>; makerspaceId?: number;
  pinned?: ReadonlySet<string>; onTogglePin?: (key: string) => void;
}) {
  return <div className="space-y-6">{groupReports(reports, pinned, t`Pinned`).map(group => <section key={group.key} aria-label={group.label}>
    <h2 className="title-panel mb-3">{group.label}</h2>
    <div className="space-y-3">{group.reports.map(report => <section key={report.key}
      className="rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center gap-2">
        <button type="button" aria-expanded={selected === report.key} onClick={() => onSelect(selected === report.key ? "" : report.key)}
          className="min-h-11 min-w-0 flex-1 rounded-control py-2 text-left font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          {report.title}{report.identity_bearing ? <span className="ml-2 text-sm text-muted">{t`Contains personal data`}</span> : null}
        </button>
        {onTogglePin ? <ReportPinButton title={report.title} pinned={pinned.has(report.key)} onToggle={() => onTogglePin(report.key)} /> : null}
      </div>
      {selected === report.key ? <ReportChartResult report={report} base={base} period={period} filters={filters} makerspaceId={makerspaceId} /> : null}
    </section>)}</div>
  </section>)}</div>;
}

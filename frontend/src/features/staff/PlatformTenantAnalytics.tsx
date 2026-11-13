import { LogoLoader } from "../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../lib/api";
import type { AnalyticsMakerspace } from "./platformAnalyticsApi";
import type { ReportCatalog } from "./panels/operationsReportsConfig";
import { periodParams, type AnalyticsPeriod, type DashboardAnalytics } from "./panels/analyticsApi";
import { ReportAreaSections } from "./panels/ReportAreaSections";
import { DashboardAnalyticsWidgets } from "./panels/DashboardAnalyticsWidgets";
import { TILES, type DashboardCounts } from "./panels/DashboardStats";

export function PlatformTenantAnalytics({ space, period, initialReport }: {
  space: AnalyticsMakerspace; period: AnalyticsPeriod; initialReport: string;
}) {
  const base = `/admin/platform/analytics/makerspaces/${space.id}`;
  const catalog = useQuery({ queryKey: ["platform-tenant-catalog", space.id], retry: false,
    queryFn: () => staffRequest<ReportCatalog>(`${base}/reports/catalog`) });
  const [selected, setSelected] = useState(initialReport);
  const [showDashboard, setShowDashboard] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const dashboard = useQuery({ queryKey: ["platform-tenant-dashboard", space.id], enabled: showDashboard, retry: false,
    queryFn: () => staffRequest<DashboardAnalytics & DashboardCounts>(`${base}/dashboard`) });
  if (catalog.isLoading) return <LogoLoader label={t`Loading this makerspace's reports…`} />;
  if (catalog.isError) return <div role="alert"><p>{t`Access to this makerspace's analytics is blocked or unavailable.`}</p>
    <button type="button" className="desk-button" onClick={() => void catalog.refetch()}>{t`Retry`}</button></div>;
  const reports = (catalog.data?.results ?? []).filter(report => report.available !== false);
  if (!reports.length) return <p>{t`No reports available for this makerspace.`}</p>;
  const report = reports.find(row => row.key === selected) ?? reports[0];
  async function download(format: string) {
    setExporting(true); setExportError("");
    try {
      const params = periodParams(period, report.grains);
      params.set("format", format);
      const blob = await staffRequestBlob(`${base}/reports/${encodeURIComponent(report.key)}/export?${params}`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `${space.slug}-${report.key}.${format}`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setExportError(t`Couldn't export this report. Check your access and try again.`); }
    finally { setExporting(false); }
  }
  return <div className="min-w-0 space-y-4">
    <button type="button" className="desk-button" aria-expanded={showDashboard} onClick={() => setShowDashboard(!showDashboard)}>{t`Open ${space.name} dashboard`}</button>
    {showDashboard ? <section aria-label={`${space.name} dashboard`}>
      {dashboard.isLoading ? <LogoLoader label={t`Loading dashboard…`} size={48} className="min-h-16 py-3" /> : dashboard.isError ? <div role="alert">
        <p>{t`Couldn't load this makerspace's dashboard.`}</p><button type="button" onClick={() => void dashboard.refetch()}>{t`Retry dashboard`}</button></div> : dashboard.data ? <>
        <dl className="grid gap-3 sm:grid-cols-3">{TILES.filter(tile => typeof dashboard.data?.[tile.key] === "number").map(tile =>
          <div key={tile.key}><dt>{tile.label}</dt><dd>{dashboard.data?.[tile.key]}</dd></div>)}</dl>
        <DashboardAnalyticsWidgets widgets={dashboard.data.widgets ?? []} makerspaceId={space.id} analyticsBase={`${base}/analytics`} />
      </> : null}
    </section> : null}
    {report.exportable && report.available !== false ? <div className="flex gap-2">{report.allowed_formats.map(format =>
      <button key={format} type="button" className="desk-button" disabled={exporting} onClick={() => void download(format)}>{t`Export ${format.toUpperCase()}`}</button>)}</div> : null}
    {exportError ? <p role="alert">{exportError}</p> : null}
    <ReportAreaSections reports={reports} selected={!selected ? "" : report.key}
      onSelect={setSelected} period={period} makerspaceId={space.id} base={`${base}/analytics`} />
  </div>;
}

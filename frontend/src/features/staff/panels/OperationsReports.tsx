import { ReportAreaSections } from "./ReportAreaSections";
import { ReportSelectionProvider } from "./OperationsReportSelection";
import { useEffect, useState } from "react";

import { OperationsReportExports, useOperationsReportExport } from "./OperationsReportExports";
import { SegmentedControl } from "../../../components/ui";
import { DetailLayout } from "../../../components/layouts";
import { OperationsReportNavigation, OperationsReportPicker } from "./OperationsReportNavigation";
import { ReportSchedules } from "./ReportSchedules";
import { reportFormats } from "./operationsReportsConfig";
import { type Makerspace, useStaffGet } from "./shared";
import { type ReportCatalog, type ReportKey } from "./operationsReportsConfig";
import { ServerReportViews } from "./ServerReportViews";
import type { ReportViewState } from "./reportViewsApi";
import { PAYMENT_STATUSES, PAYMENT_SUBJECTS } from "../paymentsApi";

export function OperationsReports({
  makerspace,
  isSuperadmin,
  canViewAudit,
  canManageMachines,
  canViewFinance = false,
}: {
  makerspace: Makerspace;
  makerspaces: Makerspace[];
  isSuperadmin: boolean;
  printingOnly?: boolean;
  canViewAudit: boolean;
  canManageMachines: boolean;
  canViewFinance?: boolean;
}) {
  const [rangePreset, setRangePreset] = useState("custom");
  const [schedulesOpen, setSchedulesOpen] = useState(false);
  const [exportsOpen, setExportsOpen] = useState(false);
  const [allMakerspaces, setAllMakerspaces] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [grain, setGrain] = useState("day");
  const [selectedReport, setSelectedReport] = useState<ReportKey>(() => new URLSearchParams(window.location.search).get("report") || "summary");
  const [columns, setColumns] = useState<string[]>([]);
  const [months, setMonths] = useState("");
  const [paymentStatus, setPaymentStatus] = useState("");
  const [paymentSubject, setPaymentSubject] = useState("");
  const aggregate = isSuperadmin && allMakerspaces;
  const scopeKey = aggregate ? "all" : makerspace.id;
  const analyticsBase = aggregate ? "/admin/analytics" : `/admin/makerspace/${makerspace.id}/analytics`;
  const reportsBase = aggregate ? "/admin/reports" : `/admin/makerspace/${makerspace.id}/reports`;
  const dateQuery = [startDate ? `start=${encodeURIComponent(startDate)}` : "", endDate ? `end=${encodeURIComponent(endDate)}` : ""].filter(Boolean).join("&");
  const dateSuffix = dateQuery ? `&${dateQuery}` : "";
  const reportsEnabled = aggregate || (makerspace.enabled_modules ?? []).includes("reports");
  const catalog = useStaffGet<ReportCatalog>(
    ["report-catalog", scopeKey],
    aggregate ? "/admin/reports/catalog" : `/admin/makerspace/${makerspace.id}/reports/catalog`,
    reportsEnabled,
  );
  // Off-source reports are hidden, not disabled (#183B); the server already drops them.
  const catalogEntries = reportsEnabled && !catalog.isError ? (catalog.data?.results ?? []).filter(item => item.available !== false) : [];
  useEffect(() => {
    if (!selectedReport || !catalog.data || catalogEntries.some((item) => item.key === selectedReport && item.available !== false)) return;
    const firstAvailable = catalogEntries.find((item) => item.available !== false);
    if (firstAvailable) setSelectedReport(firstAvailable.key);
  }, [catalog.data, catalogEntries, selectedReport]);
  const hardwareEnabled = canViewAudit && reportsEnabled;


  const scopeLabel = aggregate ? "all makerspaces" : makerspace.name;
  const availableExports = reportsEnabled ? catalogEntries.filter((report) => report.exportable && report.available !== false) : [];
  const selected = catalogEntries.find((report) => report.key === selectedReport);
  const effectiveGrain = (selected?.grains ?? ["day"]).includes(grain) ? grain : selected?.grains[0] ?? "day";
  const savedState: ReportViewState = {
    report_key: selectedReport, grain: effectiveGrain, columns,
    filters: { ...(startDate ? { start: startDate } : {}), ...(endDate ? { end: endDate } : {}),
      ...(months && selectedReport === "member-retention" ? { months: Number(months) } : {}),
      ...(selectedReport === "payment-reconciliation" && paymentStatus ? { status: paymentStatus } : {}),
      ...(selectedReport === "payment-reconciliation" && paymentSubject ? { subject_type: paymentSubject } : {}) },
  };
  const applyView = (state: ReportViewState) => {
    setRangePreset("custom");
    setStartDate(state.filters.start ?? ""); setEndDate(state.filters.end ?? "");
    setSelectedReport(state.report_key); setGrain(state.grain); setColumns(state.columns);
    setMonths(state.filters.months ? String(state.filters.months) : "");
    setPaymentStatus(state.filters.status ?? ""); setPaymentSubject(state.filters.subject_type ?? "");
  };

  const exportReport = useOperationsReportExport({ reports: availableExports, grain: effectiveGrain,
    filters: { months, status: paymentStatus, subject_type: paymentSubject }, reportsBase, dateSuffix, aggregate });
  const formats = selected ? reportFormats(selected) : [];
  const exportSelected = (format: "csv" | "xlsx") => exportReport.mutate({ report: selectedReport, format });
  const canExport = formats.length > 0 && availableExports.some(report => report.key === selectedReport);
  const setPreset = (value: string) => {
    setRangePreset(value);
    if (value === "custom") return;
    const end = new Date(); const start = new Date(); start.setDate(start.getDate() - Number(value) + 1);
    const date = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
    setStartDate(date(start)); setEndDate(date(end));
  };
  const selectReport = (key: string) => { setSelectedReport(key); setColumns([]); };

  return <>
    <DetailLayout title="Reports" width="wide" asideSide="start"
      meta={[`Operations reporting for ${scopeLabel}.`, selected?.title ?? "Choose a report"]}
      state={{ status: catalog.isLoading ? "loading" : catalog.isError ? "error" : "ready",
        error: "Couldn't load reports. Try again.", onRetry: () => void catalog.refetch() }}
      isEmpty={reportsEnabled && catalog.isSuccess && !catalogEntries.length}
      empty={{ message: "No reports available yet. Enable the reporting modules to get started." }}
      actions={{ primary: { label: "Export", pending: exportReport.isPending, pendingLabel: "Exporting…",
        disabled: !canExport, disabledReason: !canExport ? "Choose an available exportable report." : undefined, onClick: () => exportSelected(formats[0] ?? "csv") },
        secondary: !aggregate && reportsEnabled ? { label: "Schedule…", onClick: () => setSchedulesOpen(true) } : undefined,
        overflow: [...(canExport ? formats.map(format => ({ label: `Export ${format.toUpperCase()}`, onClick: () => exportSelected(format) })) : []),
          ...(availableExports.length ? [{ label: "Export any report", confirms: true, onClick: () => setExportsOpen(true) }] : [])] }}
      aside={<OperationsReportNavigation reports={catalogEntries} selected={selectedReport} onSelect={selectReport} />}
      main={<ReportSelectionProvider selected={selectedReport} columns={columns} grain={effectiveGrain} catalog={catalogEntries}
        hardware={hardwareEnabled} finance={canViewFinance || isSuperadmin} machines={canManageMachines}>
      <div className="space-y-6">
      <section aria-label="Report configuration" className="rounded-xl border border-line bg-panel p-5">
        <OperationsReportPicker reports={catalogEntries} selected={selectedReport} onSelect={selectReport} />
        <div className="mb-5"><SegmentedControl label="Date range" value={rangePreset} onChange={setPreset}
          options={[{ value: "7", label: "7 days" }, { value: "30", label: "30 days" }, { value: "90", label: "Quarter" }, { value: "custom", label: "Custom" }]} /></div>

        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0 flex-1 basis-64">
            <h3 className="title-section">
              Operations reporting for {scopeLabel}
            </h3>
            <p className="text-xs text-muted">
              Reports available for your actions and enabled modules.
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="eyebrow grid gap-1">
              <span>Start</span>
              <input className="desk-input" type="date" value={startDate} onChange={(event) => { setRangePreset("custom"); setStartDate(event.target.value); }} />
            </label>
            <label className="eyebrow grid gap-1">
              <span>End</span>
              <input className="desk-input" type="date" value={endDate} onChange={(event) => { setRangePreset("custom"); setEndDate(event.target.value); }} />
            </label>
            {selected?.grains.length ? <label className="eyebrow grid gap-1">
              <span>Grain</span>
              <select className="desk-input max-w-full" value={effectiveGrain} onChange={(event) => setGrain(event.target.value)}>
                {(selected?.grains ?? ["day"]).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label> : null}
            {isSuperadmin ? (
              <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-current"
                  checked={allMakerspaces}
                  onChange={(event) => setAllMakerspaces(event.target.checked)}
                />
                All makerspaces
              </label>
            ) : null}
          </div>
        </div>
        {catalog.error ? <div role="alert" className="mt-3 flex flex-wrap items-center gap-3 text-sm text-danger">
          <p>Couldn't load reports. Try again.{catalog.error instanceof Error && catalog.error.message ? ` ${catalog.error.message}` : ""}</p>
          <button type="button" className="desk-button" onClick={() => void catalog.refetch()}>Retry</button>
        </div> : null}
        {selectedReport === "member-retention" ? <label className="eyebrow grid gap-1 mt-3">Retention months (blank: 3, 6, 12)<input className="desk-input" type="number" min={1} max={120} value={months} onChange={(event) => setMonths(event.target.value)} /></label> : null}
        {selectedReport === "payment-reconciliation" ? <div className="flex flex-wrap gap-2 mt-3">
          <label className="eyebrow grid gap-1">Report payment status<select className="desk-input max-w-full" value={paymentStatus} onChange={(event) => setPaymentStatus(event.target.value)}><option value="">All statuses</option>{PAYMENT_STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="eyebrow grid gap-1">Report charge type<select className="desk-input max-w-full" value={paymentSubject} onChange={(event) => setPaymentSubject(event.target.value)}><option value="">All types</option>{PAYMENT_SUBJECTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div> : null}
        {!aggregate && reportsEnabled && (makerspace.enabled_features ?? []).includes("reports.saved_views") ?
          <ServerReportViews key={makerspace.id} makerspaceId={makerspace.id} state={savedState} fields={selected?.fields ?? []} onColumns={setColumns} onApply={applyView} /> : null}
        {!reportsEnabled ? <p className="mt-3 text-sm text-muted">Module disabled</p> : null}
      </section>

      {reportsEnabled ? <ReportAreaSections reports={catalogEntries} selected={selectedReport} onSelect={selectReport}
        base={analyticsBase} period={{ start: startDate, end: endDate, grain: effectiveGrain }} makerspaceId={aggregate ? undefined : makerspace.id}
        filters={{ ...(selectedReport === "member-retention" && months ? { months } : {}),
          ...(selectedReport === "payment-reconciliation" ? { status: paymentStatus, subject_type: paymentSubject } : {}) }} /> : null}
      {exportReport.error ? <p role="alert" className="text-sm text-danger">Couldn't export this report: {exportReport.error.message}</p> : null}
    {availableExports.length ? <DetailLayout presentation="drawer" open={exportsOpen} onClose={() => setExportsOpen(false)}
      title="Export reports" state={{ status: "ready" }} main={<OperationsReportExports reports={availableExports} selectedReport={selectedReport}
        onSelect={selectReport} reportsBase={reportsBase} dateSuffix={dateSuffix} grain={effectiveGrain} aggregate={aggregate}
        filters={{ months, status: paymentStatus, subject_type: paymentSubject }} />} /> : null}
    {!aggregate && reportsEnabled ? <DetailLayout presentation="drawer" open={schedulesOpen} onClose={() => setSchedulesOpen(false)}
      title="Scheduled reports" state={{ status: "ready" }} main={<ReportSchedules makerspaceId={makerspace.id}
        reports={availableExports.filter(report => report.schedulable !== false)} />} /> : null}
    </div></ReportSelectionProvider>} />

  </>;
}

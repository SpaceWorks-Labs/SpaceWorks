import { useMutation } from "@tanstack/react-query";

import { downloadStaffFile } from "../../../lib/api";
import { ReportSchedules } from "./ReportSchedules";
import { reportFormats, reportGrain, type ReportCatalog, type ReportKey } from "./operationsReportsConfig";

type ReportEntry = ReportCatalog["results"][number];

export function useOperationsReportExport({ reports, grain, filters = {}, reportsBase, dateSuffix, aggregate }: {
  reports: ReportEntry[]; grain: string; filters?: { months?: string; status?: string; subject_type?: string };
  reportsBase: string; dateSuffix: string; aggregate: boolean;
}) {
  return useMutation({
    mutationFn: ({ report, format }: { report: string; format: "csv" | "xlsx" }) => {
      const exportGrain = reportGrain(reports.find(definition => definition.key === report), grain);
      const params = new URLSearchParams();
      if (report === "member-retention" && filters.months) params.set("months", filters.months);
      if (report === "payment-reconciliation") {
        if (filters.status) params.set("status", filters.status);
        if (filters.subject_type) params.set("subject_type", filters.subject_type);
      }
      return downloadStaffFile(
        `${reportsBase}/${report}/export?format=${format}${dateSuffix}&grain=${encodeURIComponent(exportGrain)}${params.size ? `&${params}` : ""}`,
        `${aggregate ? "all-makerspaces-" : ""}${report}.${format}`,
      );
    },
  });
}

// Every exportable report with a button per format, so any report can be exported without
// selecting it first. Opened from the Reports header; schedules have their own drawer.
// It owns the export mutation (a file download, not server state, so nothing is invalidated).
export function OperationsReportExports({
  reports,
  selectedReport,
  onSelect,
  reportsBase,
  dateSuffix,
  filters = {},
  grain,
  aggregate,
  makerspaceId,
  reportsEnabled = false,
}: {
  reports: ReportEntry[];
  selectedReport: ReportKey;
  onSelect: (key: ReportKey) => void;
  reportsBase: string;
  dateSuffix: string;
  filters?: { months?: string; status?: string; subject_type?: string };
  grain: string;
  aggregate: boolean;
  /** With a makerspace, schedules render under the grid (the Reports page keeps them in their own drawer). */
  makerspaceId?: number;
  reportsEnabled?: boolean;
}) {
  const exportReport = useOperationsReportExport({ reports, grain, filters, reportsBase, dateSuffix, aggregate });

  return (
    <section aria-label="Exports">
        <div className="grid gap-3 sm:grid-cols-2">
          {reports.map((definition) => (
            <div key={definition.key} className={`rounded-md border p-3 ${selectedReport === definition.key ? "border-accent bg-accent-soft" : "border-line bg-bg"}`}>
              <h3 className="title-section">{definition.title}</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {reportFormats(definition).map((format) => (
                  <button key={format} className="desk-button" type="button" disabled={exportReport.isPending} onClick={() => { onSelect(definition.key); exportReport.mutate({ report: definition.key, format }); }}>
                    {format.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        {exportReport.error ? (
          <p role="alert" className="mt-3 rounded-md border border-danger-line bg-panel px-3 py-2 text-sm text-danger">
            {exportReport.error instanceof Error ? exportReport.error.message : "Could not export report."}
          </p>
        ) : null}
      {/* Only schedulable definitions reach schedules: email/chat delivery of e.g. the
          audit trail would broaden custody of accountability data. */}
      {makerspaceId !== undefined && !aggregate && reportsEnabled ? (
        <ReportSchedules makerspaceId={makerspaceId} reports={reports.filter((report) => report.schedulable !== false)} />
      ) : null}
    </section>
  );
}

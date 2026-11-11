import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { DrillSettingsForm } from "./DrillSettingsForm";
import { PAGE_SIZE } from "./parityRequest";
import { useDrillOverview, useDrillReports, type DrillReport } from "./restoreDrillsApi";
import { RunDrillForm } from "./RunDrillForm";

function checksText(report: DrillReport) {
  const parts: string[] = [];
  if (typeof report.checks.row_total === "number") parts.push(`${report.checks.row_total} rows`);
  if (typeof report.checks.objects_verified === "number") parts.push(`${report.checks.objects_verified} files verified`);
  if (report.outcome === "failed" && report.error_code) parts.push(`error ${report.error_code}`);
  return parts.length ? ` · ${parts.join(" · ")}` : "";
}

function Reports() {
  const [page, setPage] = useState(1);
  const list = useDrillReports(page);
  const rows = list.data?.results ?? [];
  return <section className="grid gap-3" aria-labelledby="drill-reports-heading">
    <h3 id="drill-reports-heading" className="title-section">{t`Drill reports`}</h3>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource={t`drill reports`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No drills have run yet.`} />
      : <div className="grid gap-3">{rows.map(report => <ListRow key={report.id}
        title={report.makerspace_name ?? t`Space #${report.makerspace_id} (deleted)`}
        meta={<>started <RelativeTime date={report.started_at} exact />
          {report.finished_at ? <> {t` · finished `}<RelativeTime date={report.finished_at} exact /></> : null}{checksText(report)}</>}
        right={<StatusPill label={report.outcome === "passed" ? t`Passed` : t`Failed`} tone={report.outcome === "passed" ? "success" : "danger"} />} />)}
      </div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
  </section>;
}

/** Restore drills: schedule, run one now, read the reports. Key rotation and full recovery stay on the server. */
export function RestoreDrillsSection() {
  const overview = useDrillOverview();
  const data = overview.data;
  return <div className="grid gap-6">
    {overview.isLoading ? <Skeleton className="h-32 w-full" />
      : overview.isError || !data ? <ErrorText resource={t`drill settings`} onRetry={() => { void overview.refetch(); }} />
      : <>
        {data.configured ? null : <p role="note" className="rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink">
          {t`Restore drills are not set up on this server yet, so none can run. Settings can still be saved.`}</p>}
        <section className="grid gap-3" aria-labelledby="drill-settings-heading">
          <h3 id="drill-settings-heading" className="title-section">{t`Schedule`}</h3>
          <DrillSettingsForm key={JSON.stringify(data.settings)} saved={data.settings} />
        </section>
        <section className="grid gap-3" aria-labelledby="drill-run-heading">
          <h3 id="drill-run-heading" className="title-section">{t`Run a drill now`}</h3>
          <RunDrillForm configured={data.configured} />
        </section>
      </>}
    <Reports />
    <section className="grid gap-2 rounded-xl border border-line bg-surface p-4" aria-labelledby="drill-server-heading">
      <h3 id="drill-server-heading" className="title-section">{t`Done on the server`}</h3>
      <p className="text-sm text-muted">
        {t`Platform key rotation (with the private key), whole-platform restore and recovery commands stay on the server by design.`}</p>
      {data?.key_rotation ? <p className="text-sm text-ink [overflow-wrap:anywhere]">{data.key_rotation}</p> : null}
    </section>
  </div>;
}

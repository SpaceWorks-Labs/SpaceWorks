import { t } from "@lingui/core/macro";
import { plural } from "../../lib/plural";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  issueDataExportDownload,
  listDataExports,
  requestDataExport,
  type DataExportJob,
} from "./dataExportsApi";
import { ListLayout } from "../../components/layouts";
import { ErrorText, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { adminQueryState } from "./adminPresentation";
import { getJobSession, trackJob } from "../../components/ui/jobStore";

export function DataExportsPanel({ makerspaceId }: { makerspaceId: number }) {
  const queryClient = useQueryClient();
  // Open by default: this is the disclosure people must read before requesting an export.
  const [disclosureOpen, setDisclosureOpen] = useState(true);
  const queryKey = ["data-exports", makerspaceId];
  const jobs = useQuery({
    queryKey,
    queryFn: () => listDataExports(makerspaceId),
    refetchInterval: (query) =>
      (query.state.data as DataExportJob[] | undefined)?.some(isRunning) ? 1500 : false,
  });
  const requestExport = useMutation({
    onMutate: getJobSession,
    mutationFn: () => requestDataExport(makerspaceId),
    onSuccess: (job, _variables, session) => { trackJob({ key: `export:${job.id}`, label: t`Data export`, makerspaceId, status: job.status, endpoint: `/admin/makerspace/${makerspaceId}/data-exports`, collectionId: job.id }, session); return queryClient.invalidateQueries({ queryKey }); },
  });
  const download = useMutation({
    mutationFn: (jobId: string) => issueDataExportDownload(makerspaceId, jobId),
    onSuccess: ({ url }) => {
      const link = document.createElement("a");
      link.href = url;
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      link.remove();
    },
  });
  const rows = jobs.data ?? [];

  return <ListLayout header={{ title: t`Data export`, subtitle: t`A readable copy of your space's records. Not a backup.`,
    primary: { label: t`Request export`, pending: requestExport.isPending, pendingLabel: "Requesting…", disabled: jobs.isLoading || jobs.isError || rows.some(isRunning),
      disabledReason: jobs.isLoading ? "Loading the export history." : jobs.isError ? "Retry loading the export history first." : rows.some(isRunning) ? "An export is already being built." : undefined,
      onClick: () => requestExport.mutate() } }}
    state={adminQueryState(jobs, "exports")} isEmpty={!rows.length}
    empty={{ message: t`No exports yet. Request one when you need a copy of your records.` }}
    callout={{ size: "banner", tone: "warn", lead: "Exports include member names, emails and phone numbers.", body: t`Handle the file like any personal data.`,
      action: { label: disclosureOpen ? t`Hide what's included` : t`Read what's included`, onClick: () => setDisclosureOpen(!disclosureOpen) } }}
    body={{ kind: "rows", rows: rows.map(job => <ListRow key={job.id} title={t`Export`} identity={{ kind: "date", date: job.created_at }}
      meta={<><RelativeTime date={job.created_at} /> · <StatusPill label={statusLabel(job)} tone={job.status === "failed" ? "danger" : job.status === "available" ? "success" : "warn"} />
        {typeof job.manifest.total_rows === "number" ? ` · ${plural(job.manifest.total_rows, "row")}` : ""}
        {job.status === "failed" ? <span className="mt-2 block text-danger" role="alert">{job.failure_code === "deadline_exceeded" ? t`This export took too long. Try again at a quieter time.` : job.failure_detail || t`The export failed. Request a new export to try again.`}</span> : null}
      </>} right={job.status === "available" ? <button className="desk-button" type="button" disabled={download.isPending && download.variables === job.id} onClick={() => download.mutate(job.id)}>
        {download.isPending && download.variables === job.id ? t`Preparing link…` : t`Download`}
      </button> : undefined} />) }}
    detail={<div className="mt-6 grid gap-3">
      {disclosureOpen ? <div className="rounded-xl border border-line bg-surface p-5 text-sm text-ink">
          <p className="font-semibold">{t`Read this disclosure before requesting an export`}</p>
          <p className="mt-2">
            {t`The readable archive includes makerspace-owned records, but omits credentials, bearer tokens, platform configuration, selected JSON configuration, audit metadata, and free-text form answers. It is not a migration backup.`}</p>
          <p className="mt-2">
            <span className="font-semibold">{t`It does contain member contact details.`}</span>{t`${" "}Names, email addresses and phone numbers that members supplied on your records are included in readable form. “Redacted” refers to audit metadata and form answers, not to personal data — handle the file accordingly.`}</p>
          <p className="mt-2">
            {t`The referenced-users file contains only id and username for people referenced by exported rows. This is a new intentional disclosure: the staff audit API exposes only a numeric actor id and the current console omits the actor. Usernames are identifying and can correlate a person across exports.`}</p>
        </div> : null}
      {requestExport.error ? <ErrorText message={requestExport.error.message} /> : null}
      {download.error ? <ErrorText message={download.error.message} /> : null}
    </div>} />;
}

function isRunning(job: DataExportJob) {
  return job.status === "pending" || job.status === "running";
}

function statusLabel(job: DataExportJob) {
  if (job.status === "available") return t`Ready`;
  if (job.status === "failed") return job.failure_code === "deadline_exceeded" ? t`Deadline exceeded` : t`Failed`;
  return job.status === "pending" ? t`Queued` : t`Building snapshot`;
}

import { t } from "@lingui/core/macro";
import { useEffect, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { LoaderCircle } from "lucide-react";
import { Modal } from "./Modal";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { dismissJob, jobRunning, jobStore, updateJob, type TrayJob } from "./jobStore";

function useJobStatus(job: TrayJob, poll = true) {
  const query = useQuery({ queryKey: ["job-tray", job.session, job.key],
    queryFn: async ({ signal }) => {
      const result = await staffRequest<{ status: string } | { id: string; status: string }[]>(job.endpoint, { signal });
      const row = Array.isArray(result) ? result.find(value => String(value.id) === job.collectionId) : result;
      if (!row) throw new Error(t`Job unavailable. Open its source panel to refresh the list.`);
      return row;
    },
    enabled: poll && jobRunning(job.status), retry: false,
    refetchInterval: state => poll && jobRunning(state.state.data?.status ?? job.status) ? 2000 : false });
  useEffect(() => { if (query.data?.status) updateJob(job.key, query.data.status, job.session); }, [job.key, job.session, query.data?.status]);
  return query;
}
function jobStatusLabel(status: string) {
  return ({ pending: t`Pending`, queued: t`Queued`, running: t`Running`, building: t`Building`, promoting: t`Promoting`,
    succeeded: t`Done`, completed: t`Done`, ready: t`Ready`, available: t`Ready`, failed: t`Failed`, cancelled: t`Cancelled`,
    expired: t`Expired` } as Record<string, string>)[status]
    ?? status.replace(/_/g, " ");
}
function JobPoller({ job }: { job: TrayJob }) { useJobStatus(job); return null; }
function JobStatus({ job, poll = true }: { job: TrayJob; poll?: boolean }) {
  const query = useJobStatus(job, poll);
  return <li className="flex flex-wrap items-center gap-3 border-t border-line p-3">
    <span>{job.label}</span><span className="text-sm text-muted">{jobStatusLabel(job.status)}</span>
    {query.error ? <><span className="text-sm text-danger">{t`Could not check progress.`}</span><button className="desk-button" onClick={() => void query.refetch()}>{t`Retry status`}</button></> : null}
    <button className="desk-button-ghost" aria-label={t`Dismiss ${job.label}`} onClick={() => dismissJob(job.key)}>{t`Dismiss`}</button>
  </li>;
}
export function JobTray({ makerspaceId, presentation = "details" }: { makerspaceId: number; presentation?: "details" | "pill" }) {
  const [open, setOpen] = useState(false);
  const all = useSyncExternalStore(jobStore.subscribe, jobStore.snapshot);
  const jobs = all.filter(row => row.makerspaceId === makerspaceId || row.makerspaceId === 0);
  if (!jobs.length) return null;
  const running = jobs.filter(row => jobRunning(row.status)).length;
  if (presentation === "pill") return <>
    {jobs.map(job => <JobPoller key={job.key} job={job} />)}
    <button type="button" className="desk-button w-full rounded-full text-sm" aria-haspopup="dialog" onClick={() => setOpen(true)}>
      <LoaderCircle aria-hidden="true" size={24} />{t`Background jobs (${running} running)`}</button>
    {open ? createPortal(<Modal open title={t`Background jobs`} onClose={() => setOpen(false)}>
      <p role="status" aria-live="polite" className="text-sm">{jobs.map(row => t`${row.label}: ${jobStatusLabel(row.status)}`).join(". ")}</p>
      <ul>{jobs.map(job => <JobStatus key={job.key} job={job} poll={false} />)}</ul>
    </Modal>, document.body) : null}
  </>;
  return <details className="mx-5 my-3 rounded-xl border border-line bg-panel">
    <summary className="min-h-11 cursor-pointer p-3">{t`Background jobs (${running} running)`}</summary>
    <p role="status" aria-live="polite" className="px-3 text-sm">{jobs.map(row => t`${row.label}: ${jobStatusLabel(row.status)}`).join(". ")}</p>
    <ul>{jobs.map(job => <JobStatus key={job.key} job={job} />)}</ul>
  </details>;
}

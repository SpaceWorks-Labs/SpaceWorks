import { t } from "@lingui/core/macro";
import { useSearchParams } from "react-router-dom";

import { DetailDrawer, KeyValueCard, StatusBadge } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";
import { formatDate, formatDateTime } from "../../../../lib/format";
import { useCrossLink } from "../../crossLinks/staffHref";
import { useStaffGet } from "../shared";
import { jobStatusLabel } from "./ServiceConsoleSections";

type JobRow = Partial<MachineServiceRequest> & { id: number; title: string; status: string };

/** The facts staff need about one job, with the machine as a deep link (A18). */
export function JobFacts({ job }: { job: JobRow }) {
  const link = useCrossLink();
  const machine = job.assigned_machine ?? job.machine ?? null;
  const machineHref = machine?.id ? link("machines", { machine: machine.id }) : undefined;
  const items = [
    { label: t`Status`, value: <StatusBadge status={job.status} label={jobStatusLabel(job.status)} /> },
    ...(job.machine_type ? [{ label: t`Machine type`, value: job.machine_type }] : []),
    { label: t`Machine`, value: machine ? (machineHref
      ? <a className="text-accent-ink underline underline-offset-4" href={machineHref}>{machine.name}</a> : machine.name) : t`Not assigned yet` },
    ...(job.requester_name || job.requester?.display ? [{ label: t`Member`, value: job.requester_name || job.requester?.display }] : []),
    ...(job.created_at ? [{ label: t`Requested`, value: formatDateTime(job.created_at) }] : []),
    ...(job.needed_by ? [{ label: t`Needed by`, value: formatDate(job.needed_by) }] : []),
    ...(job.estimated_minutes ? [{ label: t`Estimated time`, value: t`${job.estimated_minutes} min` }] : []),
    ...(job.copies && job.copies > 1 ? [{ label: t`Copies`, value: String(job.copies) }] : []),
    ...(job.files ? [{ label: t`Files`, value: String(job.files.length) }] : []),
    ...(job.payment ? [{ label: t`Payment`, value: job.payment.status === "pending" ? t`Waiting for payment` : t`Recorded` }] : []),
    ...(job.collected_by_name ? [{ label: t`Collected by`, value: job.collected_by_name }] : []),
  ];
  return <div className="grid gap-4">
    <KeyValueCard title={t`Job`} items={items} />
    {job.description ? <p className="whitespace-pre-wrap break-words text-sm">{job.description}</p> : null}
    {job.reason ? <p className="text-sm text-muted">{t`Note from staff: ${job.reason}`}</p> : null}
  </div>;
}

/** `?job=<id>`: a search, schedule or All jobs hit opens that one service job in a drawer. */
export function LinkedJob({ jobId }: { jobId: number }) {
  const [, setParams] = useSearchParams();
  const job = useStaffGet<JobRow>(["machine-service-job", jobId], `/admin/machine-service/requests/${jobId}`);
  const close = () => setParams((current) => { const next = new URLSearchParams(current); next.delete("job"); return next; }, { replace: true });
  return <DetailDrawer open title={job.data?.title ?? t`Job`} onClose={close}>
    <section aria-label={t`Linked job`} className="grid gap-3">
      {job.isLoading ? <p className="text-sm text-muted">{t`Loading job…`}</p> : null}
      {job.isError ? <p role="alert" className="text-sm">{t`Couldn't load this job. It may be outside your machines.`}</p> : null}
      {job.data ? <JobFacts job={job.data} /> : null}
      <button type="button" className="desk-button-ghost justify-self-start text-sm" onClick={close}>{t`Close job`}</button>
    </section>
  </DetailDrawer>;
}

// Printer jobs for this type's connected printers: send the in-progress request running on a
// machine to its printer, follow progress, and apply a reported result through the normal
// job workflow (completion, usage and consumables are applied server-side).
import { LogoLoader } from "../../../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, StatusPill } from "../../../../../components/ui";
import type { Machine } from "../../../machinesApi";
import { useJobBoard } from "../machineJobsApi";
import { useJobMutation, usePrinterJob, usePrinterJobs, type PrinterBinding, type PrinterJob, type PrinterJobState } from "./printerApi";
import { BoxArt } from "../../../../../components/BoxSpinner";

const STATE: Record<PrinterJobState, { label: string; tone: "neutral" | "accent" | "warn" | "success" | "danger" }> = {
  awaiting: { label: t`Sent, waiting for the printer`, tone: "accent" }, reported: { label: t`Result reported`, tone: "warn" },
  applied: { label: t`Applied`, tone: "success" }, needs_review: { label: t`Needs review`, tone: "danger" },
  cancelled: { label: t`Cancelled`, tone: "neutral" },
};
const APPLIABLE = new Set<PrinterJobState>(["reported", "needs_review"]);

export function PrinterJobsList({ makerspaceId, machineTypeId, machines, bindings, deviceName }: {
  makerspaceId: number; machineTypeId: number; machines: Machine[]; bindings: PrinterBinding[]; deviceName: (id: string) => string;
}) {
  const jobs = usePrinterJobs(makerspaceId);
  const apply = useJobMutation(makerspaceId);
  const [open, setOpen] = useState<string | null>(null);
  const machineIds = new Set(machines.map(machine => machine.id));
  const rows = (jobs.data?.results ?? []).filter(job => job.machine !== null && machineIds.has(job.machine));
  return <div className="grid gap-3 border-t border-line pt-3">
    <h4 className="text-sm font-semibold text-ink">{t`Printer jobs`}</h4>
    <SendJob makerspaceId={makerspaceId} machineTypeId={machineTypeId} bindings={bindings.filter(row => row.enabled)}
      label={row => `${deviceName(row.device)} · ${machines.find(machine => machine.id === row.machine)?.name ?? ""}`} />
    {jobs.error ? <ErrorBlock error={jobs.error} resource={t`printer jobs`} onRetry={() => void jobs.refetch()} /> : null}
    {jobs.isSuccess && !rows.length ? <p className="text-sm text-muted">{t`No printer jobs yet.`}</p> : null}
    <ul className="grid gap-2" aria-label={t`Printer jobs`}>
      {rows.map(job => <li key={job.id} className="grid gap-2 rounded-control border border-line p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="min-w-0 flex-1 text-sm"><strong className="block text-ink">{job.service_request_name} · {job.machine_name}</strong>
            <span className="text-muted [overflow-wrap:anywhere]">{job.external_job_id}{job.progress_percent !== null && job.state === "awaiting" ? ` · ${job.progress_percent}%` : ""}</span></span>
          <StatusPill tone={STATE[job.state].tone} label={STATE[job.state].label} />
          <button type="button" className="desk-button-ghost min-h-11" aria-expanded={open === job.id}
            onClick={() => setOpen(open === job.id ? null : job.id)}>{open === job.id ? t`Hide details` : t`Details`}</button>
          {APPLIABLE.has(job.state) ? <button type="button" className="desk-button-primary min-h-11" disabled={apply.isPending}
            onClick={() => apply.mutate({ apply: job.id })}>{t`Apply result`}</button> : null}
        </div>
        {open === job.id ? <JobDetail id={job.id} /> : null}
      </li>)}
    </ul>
    {apply.error ? <ErrorBlock error={apply.error} /> : null}
  </div>;
}

function JobDetail({ id }: { id: string }) {
  const detail = usePrinterJob(id);
  if (detail.isLoading) return <LogoLoader label={t`Loading job…`} size={48} className="min-h-16 py-3" />;
  if (detail.error || !detail.data) return <ErrorBlock error={detail.error} resource={t`printer job`} />;
  const job: PrinterJob = detail.data;
  const facts = [
    [t`Outcome`, job.outcome === "completed" ? t`Completed` : job.outcome === "failed" ? t`Failed` : t`Not reported yet`],
    [t`Minutes`, job.actual_minutes ?? "—"], [t`Grams`, job.actual_grams ?? "—"], [t`Quantity`, job.actual_quantity ?? "—"],
    ...(job.outcome === "failed" ? [[t`Failure`, `${job.failure_reason} (${job.percent_complete ?? 0}%)`]] : []),
    [t`Consumables`, job.consumptions.length ? job.consumptions.map(row => row.quantity).join(", ") : "—"],
  ];
  return <dl className="grid gap-1 text-sm sm:grid-cols-2">
    {facts.map(([term, value]) => <div key={String(term)} className="flex gap-2"><dt className="text-muted">{term}</dt><dd className="text-ink">{value}</dd></div>)}
  </dl>;
}

function SendJob({ makerspaceId, machineTypeId, bindings, label }: {
  makerspaceId: number; machineTypeId: number; bindings: PrinterBinding[]; label: (row: PrinterBinding) => string;
}) {
  const board = useJobBoard(makerspaceId, machineTypeId, bindings.length > 0);
  const send = useJobMutation(makerspaceId);
  const [bindingId, setBindingId] = useState("");
  const [requestId, setRequestId] = useState("");
  const [externalId, setExternalId] = useState("");
  const binding = bindings.find(row => row.id === bindingId);
  const running = board.data?.lanes.find(lane => lane.machine_id === binding?.machine)?.running ?? [];
  if (!bindings.length) return null;
  return <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
    event.preventDefault();
    send.mutate({ create: { binding_id: bindingId, service_request_id: Number(requestId), external_job_id: externalId.trim() } },
      { onSuccess: () => { setRequestId(""); setExternalId(""); } });
  }}>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Printer`}</span>
      <select className="desk-input min-h-11" value={bindingId} onChange={event => { setBindingId(event.target.value); setRequestId(""); }}>
        <option value="">{t`Choose a printer…`}</option>
        {bindings.map(row => <option key={row.id} value={row.id}>{label(row)}</option>)}</select></label>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Running job`}</span>
      <select className="desk-input min-h-11" value={requestId} disabled={!binding} onChange={event => setRequestId(event.target.value)}>
        <option value="">{binding && !running.length ? t`Nothing running on this machine` : t`Choose a job…`}</option>
        {running.map(job => <option key={job.id} value={job.id}>{job.title || t`Request ${job.id}`}</option>)}</select></label>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Printer job name`}</span>
      <input className="desk-input min-h-11" value={externalId} maxLength={120} placeholder={t`File or job name on the printer`}
        onChange={event => setExternalId(event.target.value)} /></label>
    <button type="submit" className="desk-button min-h-11" disabled={!bindingId || !requestId || !externalId.trim() || send.isPending}>
      {send.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send to printer`}</button>
    {send.error ? <div className="basis-full"><ErrorBlock error={send.error} /></div> : null}
  </form>;
}

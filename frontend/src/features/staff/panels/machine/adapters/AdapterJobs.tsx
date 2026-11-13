import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorBlock, StatusPill } from "../../../../../components/ui";
import { getMachines, machineKeys } from "../../../machinesApi";
import { useJobBoard } from "../machineJobsApi";
import { useJobMutation } from "../integrations/printerApi";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Binding, type BindingJob } from "./adaptersApi";
import { BoxArt } from "../../../../../components/BoxSpinner";

type State = BindingJob["state"];
const STATE: Record<State, { label: string; tone: "neutral" | "accent" | "warn" | "success" | "danger" }> = {
  awaiting: { label: t`Sent, waiting for the adapter`, tone: "accent" }, reported: { label: t`Result reported`, tone: "warn" },
  applied: { label: t`Applied`, tone: "success" }, needs_review: { label: t`Needs review`, tone: "danger" }, cancelled: { label: t`Cancelled`, tone: "neutral" },
};

/** Jobs of one machine through its adapter: send the running request, then review and apply the reported result (the existing machine-service review). */
export function AdapterJobs({ makerspaceId, binding, disabled }: { makerspaceId: number; binding: Binding; disabled: boolean }) {
  const client = useQueryClient();
  const machines = useQuery({ queryKey: machineKeys.list(makerspaceId), queryFn: () => getMachines(makerspaceId) });
  const typeId = machines.data?.results.find(row => row.id === binding.machine_id)?.machine_type?.id ?? 0;
  const board = useJobBoard(makerspaceId, typeId, typeId > 0);
  const [state, setState] = useState("");
  const [page, setPage] = useState(1);
  const query = new URLSearchParams({ page: String(page), ...(state ? { state } : {}) }).toString();
  const jobs = useQuery({ queryKey: adapterKeys.bindingJobs(makerspaceId, binding.id, query), queryFn: () => adaptersApi.bindingJobs(binding.id, query) });
  const apply = useJobMutation(makerspaceId);
  const [requestId, setRequestId] = useState("");
  const running = board.data?.lanes?.find(lane => lane.machine_id === binding.machine_id)?.running ?? [];
  const refresh = () => { void client.invalidateQueries({ queryKey: ["device-adapters", makerspaceId, "binding-jobs", binding.id] }); };
  const send = useMutation({ mutationFn: () => adaptersApi.dispatchJob(binding.id, Number(requestId)), onSuccess: () => { setRequestId(""); refresh(); } });
  const rows = jobs.data?.results ?? [];
  return <details className="text-sm"><summary className="cursor-pointer font-semibold">{t`Jobs`}</summary>
    <div className="mt-3 grid gap-3">
      <form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); if (requestId) send.mutate(); }}>
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Running job`}</span>
          <select className="desk-input min-h-11" value={requestId} disabled={disabled} onChange={event => setRequestId(event.target.value)}>
            <option value="">{running.length ? t`Choose a job…` : t`Nothing running on this machine`}</option>
            {running.map(job => <option key={job.id} value={job.id}>{job.title || t`Request ${job.id}`}</option>)}</select></label>
        <button type="submit" className="desk-button min-h-11" disabled={disabled || !requestId || send.isPending}>{send.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send to adapter`}</button>
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Show`}</span>
          <select className="desk-input min-h-11" value={state} onChange={event => { setState(event.target.value); setPage(1); }}>
            <option value="">{t`All jobs`}</option>{(Object.keys(STATE) as State[]).map(key => <option key={key} value={key}>{STATE[key].label}</option>)}</select></label>
      </form>
      {send.isError ? <p role="alert" className="text-danger">{adapterErrorMessage(send.error)}</p> : null}
      {jobs.error ? <ErrorBlock error={jobs.error} resource={t`jobs`} onRetry={() => void jobs.refetch()} /> : null}
      {jobs.isSuccess && !rows.length ? <p className="text-muted">{t`No jobs match.`}</p> : null}
      <ul className="grid gap-2" aria-label={t`Adapter jobs`}>{rows.map(job => <li key={job.id} className="flex flex-wrap items-center gap-2 rounded-control border border-line p-3">
        <span className="min-w-0 flex-1"><strong className="block text-ink">{job.service_request_name}</strong>
          <span className="text-muted">{job.progress_percent !== null && job.state === "awaiting" ? `${job.progress_percent}%` : job.outcome === "completed" ? t`Completed` : job.outcome === "failed" ? t`Failed` : ""}
            {job.command_error ? ` ${t`Adapter error: ${job.command_error}`}` : ""}{job.failure_reason ? ` ${job.failure_reason}` : ""}</span></span>
        <StatusPill tone={STATE[job.state].tone} label={STATE[job.state].label} />
        {job.state === "reported" || job.state === "needs_review" ? <button type="button" className="desk-button-primary min-h-11" disabled={apply.isPending}
          onClick={() => apply.mutate({ apply: job.id }, { onSuccess: refresh })}>{job.state === "needs_review" ? t`Review and apply` : t`Approve result`}</button> : null}
      </li>)}</ul>
      {jobs.data && (jobs.data.previous || jobs.data.next) ? <div className="flex gap-2">
        <button type="button" className="desk-button" disabled={!jobs.data.previous} onClick={() => setPage(page - 1)}>{t`Previous`}</button>
        <button type="button" className="desk-button" disabled={!jobs.data.next} onClick={() => setPage(page + 1)}>{t`Next`}</button></div> : null}
      {apply.error ? <ErrorBlock error={apply.error} /> : null}
    </div>
  </details>;
}

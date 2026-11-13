// Bulk card jobs (all cards as one PDF, one PDF each in a ZIP, or one email each) run on
// the server in chunks. The page polls the job, shows progress, offers cancel, and fetches a
// short-lived private link once the file is ready (kept 7 days).
import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";

export type CardJobKind = "bulk_sheet" | "bulk_per_person" | "zip" | "email";

export type CardJob = {
  id: number; kind: CardJobKind | "photo_cleanup" | "wallet_issue" | "wallet_update"; scope: string; scope_id: number;
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled"; total: number; done: number; failed: number;
  progress: number; error_code: string; download_ready: boolean; result_expires_at: string | null;
  created_at: string; started_at: string | null; finished_at: string | null;
};

export const JOB_LABELS: Record<CardJobKind, string> = {
  bulk_sheet: t`All cards (PDF)`, bulk_per_person: t`One PDF per card`, zip: t`All cards (ZIP)`, email: t`Email all cards`,
};

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);
export const isTerminal = (job: CardJob) => TERMINAL.has(job.state);

export function useCardJobs(listPath: string) {
  return useQuery({
    queryKey: ["card-jobs", listPath],
    queryFn: () => staffRequest<CardJob[]>(listPath),
    refetchInterval: (query) => ((query.state.data ?? []).some((job) => !isTerminal(job)) ? 2000 : false),
  });
}

export function useStartCardJob(listPath: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      staffRequest<CardJob>(listPath, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["card-jobs", listPath] }),
  });
}

export function useCancelCardJob(listPath: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => staffRequest<CardJob>(`/admin/card-jobs/${id}/cancel`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["card-jobs", listPath] }),
  });
}

export async function openJobResult(id: number) {
  const link = await staffRequest<{ url: string }>(`/admin/card-jobs/${id}/result`);
  window.location.assign(link.url);
}

const STATE_LABELS: Record<CardJob["state"], string> = {
  queued: t`Waiting to start`, running: t`Working`, succeeded: t`Ready`, failed: t`Failed`, cancelled: t`Cancelled`,
};

/** The latest few jobs with their progress; the newest unfinished one first. */
export function CardJobList({ listPath }: { listPath: string }) {
  const jobs = useCardJobs(listPath);
  const cancel = useCancelCardJob(listPath);
  const rows = (jobs.data ?? []).slice(0, 5);
  if (!rows.length) return null;
  return <ul className="grid gap-2" aria-label={t`Card jobs`}>
    {rows.map((job) => <li key={job.id} className="grid gap-1 rounded-control border border-line bg-panel p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-ink">{JOB_LABELS[job.kind as CardJobKind] ?? t`Card job`}</span>
        <span className="text-muted">{STATE_LABELS[job.state]}{job.total ? t` · ${job.done} of ${job.total}` : ""}
          {job.failed ? t` · ${job.failed} could not be made` : ""}</span>
      </div>
      {!isTerminal(job) ? <div className="h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0}
        aria-valuemax={100} aria-valuenow={job.progress} aria-label={t`Progress`}>
        <div className="h-full bg-accent-ink motion-safe:transition-[width]" style={{ width: `${job.progress}%` }} />
      </div> : null}
      <div className="flex flex-wrap gap-2">
        {!isTerminal(job) ? <button type="button" className="desk-button-ghost min-h-11" disabled={cancel.isPending}
          onClick={() => cancel.mutate(job.id)}>{t`Cancel`}</button> : null}
        {job.download_ready ? <button type="button" className="desk-button min-h-11"
          onClick={() => void openJobResult(job.id).catch(() => undefined)}>{t`Download`}</button> : null}
        {job.download_ready && job.result_expires_at ? <span className="self-center text-xs text-muted">
          {t`Kept until ${new Date(job.result_expires_at).toLocaleDateString(formatLocale())}`}</span> : null}
        {job.state === "failed" ? <span className="self-center text-xs text-danger">{t`The job stopped. Try again.`}</span> : null}
      </div>
    </li>)}
  </ul>;
}

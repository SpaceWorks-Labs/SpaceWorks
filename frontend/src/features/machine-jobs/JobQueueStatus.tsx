import { StatusPill } from "../../components/ui";
import { minutesLabel } from "../machine-service/ServiceRequestEta";
import { etaWhen, type MemberJob } from "./types";

/** "#3 in queue" or "You're next", and when it should start and be ready. Server values only. */
export function JobQueueStatus({ job, now = new Date() }: { job: Pick<MemberJob, "label" | "position" | "eta">; now?: Date }) {
  const queued = job.label === "in_queue";
  const running = job.label === "in_progress";
  if (!queued && !running) return null;
  const eta = job.eta;
  const known = eta && eta.confidence !== "unavailable" && eta.estimated_finish_at;
  const when = (iso: string) => etaWhen(iso, now, minutesLabel);
  return <div className="grid gap-2" data-testid="job-queue-status">
    {queued && job.position != null ? <p className="title-section text-ink">
      {job.position <= 1 ? "You're next" : <><span className="tabular-nums">#{job.position}</span> in queue</>}</p> : null}
    {running ? <p className="title-section text-ink">Your job is running</p> : null}
    {known ? <p className="flex flex-wrap items-center gap-2 text-sm text-ink">
      <span>{queued && eta.estimated_start_at ? `Should start ${when(eta.estimated_start_at)} · ` : ""}ready {when(eta.estimated_finish_at!)}</span>
      <span className="text-muted">(estimate)</span>
      {eta.confidence === "rough" ? <StatusPill label="Rough estimate" tone="warn" /> : null}
    </p> : <p className="text-sm text-muted">We can't estimate a time yet.</p>}
    {eta ? <p className="text-xs text-muted">Estimates depend on the machines and on staff being there; they update as the queue moves.</p> : null}
  </div>;
}

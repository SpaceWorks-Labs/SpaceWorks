import { StatusPill } from "../../components/ui";
import type { EtaReason, ServiceRequestEta as Eta } from "./types";
import { normalizeServiceStatus } from "./types";

// Server values only: the browser never sums a queue, decrements a countdown or derives a
// finish time. A stale snapshot is labelled with when it was calculated, never "corrected".
const REASON_TEXT: Record<EtaReason, string> = {
  awaiting_approval: "Staff still need to approve this job.",
  missing_estimate: "A job in line (or this one) has no time estimate yet.",
  no_active_machine: "No compatible machine is available right now.",
  overdue_running_job: "A running job is taking longer than estimated.",
  unknown_running_job: "A machine's current job has no reliable end time.",
  inactive_scope: "This queue is paused.",
  competing_scopes: "These machines are shared with other queues.",
};

export function minutesLabel(minutes: number): string {
  if (minutes <= 0) return "now";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `about ${rest} min`;
  return rest ? `about ${hours} h ${rest} min` : `about ${hours} h`;
}

function sameLocalDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** Local wall time with an explicit timezone label; the date appears once it is not today. */
export function clockLabel(iso: string, reference: Date): string {
  const date = new Date(iso);
  const options: Intl.DateTimeFormatOptions = sameLocalDay(date, reference)
    ? { hour: "2-digit", minute: "2-digit", timeZoneName: "short" }
    : { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short" };
  return new Intl.DateTimeFormat(undefined, options).format(date);
}

function Clock({ iso, reference }: { iso: string; reference: Date }) {
  return <time dateTime={iso}>{clockLabel(iso, reference)}</time>;
}

function headline(eta: Eta, status: string, reference: Date) {
  const finish = eta.estimated_finish_at;
  if (eta.confidence === "unavailable" || !finish || eta.start_in_minutes == null) return null;
  if (status === "in_progress") {
    return <>Done around <Clock iso={finish} reference={reference} /> <span className="text-muted">(estimate)</span></>;
  }
  const start = eta.start_in_minutes <= 0 ? "Could start now" : `Starts in ${minutesLabel(eta.start_in_minutes)}`;
  return <>{start} · done around <Clock iso={finish} reference={reference} /> <span className="text-muted">(estimate)</span></>;
}

function lineCopy(eta: Eta, status: string): string | null {
  if (status === "pending") {
    const pending = eta.awaiting_review_ahead;
    return eta.approved_ahead === 0 && pending === 0
      ? "Awaiting review"
      : `Awaiting review · ${eta.approved_ahead} approved ahead · ${pending} awaiting review ahead`;
  }
  if (status === "accepted") {
    return eta.approved_ahead === 0
      ? "You're next among approved jobs"
      : `${eta.approved_ahead} approved job${eta.approved_ahead === 1 ? "" : "s"} ahead of you`;
  }
  return null;
}

/** The one ETA presentation shared by status pages, the member dashboard and staff consoles. */
export function ServiceRequestEta({ eta, status, compact = false, showLine = true, now }: {
  eta: Eta | null | undefined; status: string; compact?: boolean; showLine?: boolean; now?: Date;
}) {
  if (!eta) return null;
  const normalized = normalizeServiceStatus(status);
  const reference = now ?? new Date();
  const lead = headline(eta, normalized, reference);
  const line = showLine ? lineCopy(eta, normalized) : null;
  const pill = eta.confidence === "unavailable"
    ? <StatusPill label="Estimate unavailable" tone="neutral" />
    : normalized === "pending"
      ? <StatusPill label="If approved" tone="warn" />
      : eta.confidence === "rough" ? <StatusPill label="Rough estimate" tone="warn" /> : null;
  const reasons = eta.reasons.filter(reason => reason !== "awaiting_approval" || normalized !== "pending");
  if (compact) {
    return <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink">
      {lead ?? <span className="text-muted">Estimate unavailable</span>}
      {lead && pill && eta.confidence !== "estimated" ? pill : null}
      {line ? <span className="text-muted">{line}</span> : null}
    </span>;
  }
  return <div className="grid gap-2 text-sm text-ink" data-testid="service-request-eta">
    <div className="flex flex-wrap items-center gap-2">
      {lead ? <p className="font-semibold">{lead}</p> : <p className="font-semibold">We can't estimate a time yet.</p>}
      {pill}
    </div>
    {line ? <p className="text-muted">{line}</p> : null}
    {reasons.length ? <ul className="grid gap-1 text-muted">{reasons.map(reason => <li key={reason}>{REASON_TEXT[reason]}</li>)}</ul> : null}
    <p className="text-xs text-muted">
      Estimates assume continuous machine time and depend on staff availability. Updated <Clock iso={eta.calculated_at} reference={reference} />.
    </p>
  </div>;
}

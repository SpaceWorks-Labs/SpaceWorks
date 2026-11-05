import { useEffect, useState } from "react";

/** S13: every stage deadline in the event's time zone AND the viewer's own, with a live countdown. */
export function inZone(iso: string, timeZone?: string) {
  try {
    return new Intl.DateTimeFormat(undefined, { timeZone, dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return new Date(iso).toLocaleString();
  }
}

export function viewerZone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

export function deadlineText(iso: string, eventZone: string) {
  const local = viewerZone();
  const event = `${inZone(iso, eventZone)} (${eventZone})`;
  return local === eventZone ? event : `${event} · ${inZone(iso, local)} your time`;
}

export function countdownTo(iso: string, now: number) {
  const left = Date.parse(iso) - now;
  if (!Number.isFinite(left)) return "";
  if (left <= 0) return "Deadline passed";
  const minutes = Math.ceil(left / 60_000);
  if (minutes >= 1440) return `${Math.floor(minutes / 1440)}d ${Math.floor((minutes % 1440) / 60)}h left`;
  if (minutes >= 60) return `${Math.floor(minutes / 60)}h ${minutes % 60}m left`;
  return `${minutes}m left`;
}

export function useMinuteClock() {
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer); }, []);
  return now;
}

export function Countdown({ deadline }: { deadline: string }) {
  const now = useMinuteClock();
  return <span className="text-sm font-semibold text-accent-ink">{countdownTo(deadline, now)}</span>;
}

/** A public, read-only list of stage deadlines (event page). */
export type PublicStage = { position: number; name: string; opens_at: string | null; deadline: string };

export function PublicStageDeadlines({ stages, timeZone }: { stages: readonly PublicStage[]; timeZone: string }) {
  const now = useMinuteClock();
  const next = stages.find(stage => Date.parse(stage.deadline) > now);
  return <ol className="grid gap-3">
    {stages.map(stage => <li key={stage.position} className="grid gap-1 rounded-2xl border border-line p-3">
      <span className="font-semibold text-ink">{`${stage.position}. ${stage.name}`}</span>
      <span className="text-sm text-muted">{`Deadline: ${deadlineText(stage.deadline, timeZone)}`}</span>
      {next?.position === stage.position ? <span className="text-sm font-semibold text-accent-ink">{countdownTo(stage.deadline, now)}</span> : null}
    </li>)}
  </ol>;
}

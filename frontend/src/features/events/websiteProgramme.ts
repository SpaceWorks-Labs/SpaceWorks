import type { WebsiteSession as ProjectedSession } from "../../generated/api";
import type { WebsiteSession } from "./websiteTypes";

/** Match the server projection using the draft's planned order, tracks and visibility. */
export function previewSessions(sessions: WebsiteSession[]): ProjectedSession[] {
  const delays = new Map<string | null, number>();
  const planned = (value: string) => Date.parse(value) || 0;
  const shifted = (value: string, minutes: number) => {
    const time = Date.parse(value);
    return Number.isFinite(time) ? new Date(time + minutes * 60_000).toISOString() : undefined;
  };
  return [...sessions].sort((a, b) => planned(a.starts_at) - planned(b.starts_at)
    || (a.slug < b.slug ? -1 : a.slug > b.slug ? 1 : 0)).map((row) => {
    const delay = Math.max(delays.get(row.track ?? null) ?? 0, row.delay_minutes ?? 0);
    // A draft session gets its own preview delay but cannot shift published sessions.
    if (row.visibility === "published") delays.set(row.track ?? null, delay);
    return { ...row, delay_minutes: row.delay_minutes ?? 0, effective_starts_at: shifted(row.starts_at, delay) ?? row.starts_at, effective_ends_at: shifted(row.ends_at, delay) ?? row.ends_at };
  });
}

/** Simultaneous sessions in separate tracks are expected; competing resources get warnings. */
export function programmeWarnings(sessions: WebsiteSession[]) {
  const warnings: string[] = [];
  sessions.forEach((session, index) => sessions.slice(index + 1).forEach((other) => {
    if (!(Date.parse(session.starts_at) < Date.parse(other.ends_at) && Date.parse(other.starts_at) < Date.parse(session.ends_at))) return;
    const reasons = [session.track === other.track ? "track" : "",
      session.room && session.room === other.room ? "room" : "",
      (session.speakers ?? []).some((speaker) => (other.speakers ?? []).includes(speaker)) ? "speaker" : ""].filter(Boolean);
    if (reasons.length) warnings.push(`${session.title || session.slug} overlaps ${other.title || other.slug}: shared ${reasons.join(", ")}.`);
  }));
  return warnings;
}

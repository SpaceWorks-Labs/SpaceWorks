import { useEffect, useRef, useState } from "react";
import type { PresenceSession } from "./api";
import { clockTime, minutesLeft } from "./presenceCopy";
import { showWebNotification } from "./webNotify";

/** Matches the server: a session may renew up to 10 minutes after it expired. */
export const RENEW_WINDOW_MINUTES = 10;

export type RenewPhase = "none" | "soon" | "expired" | "gone";

export function renewPhase(session: Pick<PresenceSession, "expires_at" | "ended_at" | "end_reason"> | null, now: number): RenewPhase {
  if (!session) return "none";
  // Ended by the person or by staff: renewing is refused, a new check-in is needed.
  if (session.ended_at && session.end_reason !== "expired") return "gone";
  const left = minutesLeft(session, now);
  if (left > RENEW_WINDOW_MINUTES) return "none";
  if (left > 0) return "soon";
  return new Date(session.expires_at).getTime() >= now - RENEW_WINDOW_MINUTES * 60_000 ? "expired" : "gone";
}

/** A clock that re-renders often enough for minute-granularity countdowns. */
export function useNow(intervalMs = 15_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** One local web notification per session expiry and phase; never repeats on re-render. */
export function useRenewNotification(session: PresenceSession | null, phase: RenewPhase, spaceName: string) {
  const sent = useRef(new Set<string>());
  useEffect(() => {
    if (!session || (phase !== "soon" && phase !== "expired")) return;
    const key = `${session.expires_at}:${phase}`;
    if (sent.current.has(key)) return;
    sent.current.add(key);
    const body = phase === "soon"
      ? `Your check-in ends at ${clockTime(session.expires_at)}. Open Space Works to renew.`
      : `Your check-in ended at ${clockTime(session.expires_at)}. Still here? Renew within ${RENEW_WINDOW_MINUTES} minutes.`;
    void showWebNotification(`${spaceName}: check-in ${phase === "soon" ? "ending" : "ended"}`, body, `presence-${session.expires_at}`);
  }, [session, phase, spaceName]);
}

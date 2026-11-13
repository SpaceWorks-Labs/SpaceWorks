// In-memory timer/fullscreen helpers. The offline adapter owns encrypted loaded
// leases/packages and explicit key destruction; the Station cookie stays HttpOnly.
// Fullscreen and wake lock are usability controls only; they grant nothing.
import { useEffect, useRef, useState } from "react";

export const KIOSK_IDLE_RESET_MS = 5 * 60 * 1000;
const ACTIVITY_EVENTS = ["pointerdown", "keydown", "touchstart"] as const;

/** True once `expiresAt` (ISO) is within `skewMs` of now, or unparsable. */
export function isExpired(expiresAt: string | null | undefined, now = Date.now(), skewMs = 5000) {
  if (!expiresAt) return true;
  const at = Date.parse(expiresAt);
  return Number.isNaN(at) || at - skewMs <= now;
}

/** Milliseconds until the earlier of the idle limit and the server expiry. */
export function resetDelay(expiresAt: string | null | undefined, now = Date.now(), idleMs = KIOSK_IDLE_RESET_MS) {
  if (!expiresAt) return idleMs;
  const at = Date.parse(expiresAt);
  return Number.isNaN(at) ? 0 : Math.max(0, Math.min(idleMs, at - now));
}

/** Call `onReset` after inactivity, or when the session/lease expiry passes. */
export function useIdleReset(active: boolean, expiresAt: string | null | undefined, onReset: () => void) {
  const callback = useRef(onReset);
  const bumpRef = useRef<() => void>(() => undefined);
  const [seconds, setSeconds] = useState<number | null>(null);
  useEffect(() => { callback.current = onReset; }, [onReset]);
  useEffect(() => {
    setSeconds(null);
    if (!active) return undefined;
    let resetTimer: number;
    let warningTimer: number;
    let countdownTimer: number | undefined;
    const clear = () => {
      window.clearTimeout(resetTimer);
      window.clearTimeout(warningTimer);
      window.clearInterval(countdownTimer);
    };
    const bump = () => {
      clear(); setSeconds(null);
      const delay = resetDelay(expiresAt);
      const deadline = Date.now() + delay;
      resetTimer = window.setTimeout(() => { clear(); setSeconds(null); callback.current(); }, delay);
      warningTimer = window.setTimeout(() => {
        const tick = () => setSeconds(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
        tick(); countdownTimer = window.setInterval(tick, 1000);
      }, Math.max(0, delay - 10_000));
    };
    bumpRef.current = bump;
    bump();
    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, bump));
    return () => {
      clear(); bumpRef.current = () => undefined;
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, bump));
    };
  }, [active, expiresAt]);
  return { seconds, onKeep: () => bumpRef.current() };
}

/** Best-effort fullscreen + screen wake lock; failures are silently ignored. */
export async function enterKioskMode() {
  try { await document.documentElement.requestFullscreen?.(); } catch { /* not allowed */ }
  try {
    const wakeLock = (navigator as Navigator & { wakeLock?: { request: (type: "screen") => Promise<unknown> } }).wakeLock;
    await wakeLock?.request("screen");
  } catch { /* unsupported */ }
}

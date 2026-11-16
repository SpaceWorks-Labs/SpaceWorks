import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { DisplayHttpError, displayScreenApi, type DisplayPanel, type DisplayRegistration, type DisplayState } from "./api";

export const TOKEN_KEY = "sw-space-display-token";
export const POLL_UNCLAIMED_MS = 4_000;
export const POLL_PAIRED_MS = 10_000;
export const RETRY_MS = 5_000;
/** After this many failed polls in a row, the next good answer reloads the page: a TV that sat offline for
 * minutes comes back with fresh scripts rather than a half-stale tab (Anthias keeps one tab open for days). */
const RELOAD_AFTER_FAILURES = 3;

/** A staff-issued address carries the secret in the fragment (`/display#k=...`): browsers never send a
 * fragment, and polls carry it in the Authorization header, so it never appears in a request line. */
export function linkToken(): string | null {
  try { return new URLSearchParams(window.location.hash.replace(/^#/, "")).get("k"); } catch { return null; }
}

const store = {
  read: () => { try { return window.localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  write: (value: string | null) => { try { if (value) window.localStorage.setItem(TOKEN_KEY, value); else window.localStorage.removeItem(TOKEN_KEY); } catch { /* private mode: the screen re-pairs on reload */ } },
};

/** One registration at a time per page: StrictMode effect replay and remounts share it instead of
 * minting a second screen (arch review 8). Cleared once it settles so a later reset can register again. */
let pendingRegistration: Promise<DisplayRegistration> | null = null;
export function registerOnce(): Promise<DisplayRegistration> {
  pendingRegistration ??= displayScreenApi.register().finally(() => { pendingRegistration = null; });
  return pendingRegistration;
}

export const displayStateKey = (token: string) => ["space-display", "state", token] as const;

export type ScreenView = {
  /** The last good state; kept while offline so the room never goes blank. */
  state: DisplayState | null;
  /** True while the last poll failed: show "Reconnecting". */
  reconnecting: boolean;
  /** The server no longer knows this screen (unpaired, switched off): a fresh code is being fetched. */
  reset: boolean;
  /** The address's own secret was revoked: it cannot register again, so say so instead of showing a code. */
  linkRevoked: boolean;
  updatedAt: number | null;
};

const isGone = (error: unknown) => error instanceof DisplayHttpError && error.status === 404;

/** Poll gap: fast while waiting to be paired, the staff-set refresh once paired, RETRY_MS after a failure. */
function nextPoll(data: DisplayState | undefined, failed: boolean): number {
  if (failed || !data) return RETRY_MS;
  return data.state === "unclaimed" ? POLL_UNCLAIMED_MS : (data.config.refresh_seconds || POLL_PAIRED_MS / 1000) * 1000;
}

/**
 * The screen's whole life: register, show the code, poll until staff claim it, then poll for panel and
 * data changes. Polling is a token-keyed TanStack query (server state, cancelled on unmount); a 404 means
 * unpaired/unknown/switched off, so the secret is dropped and, after RETRY_MS, a new one is requested.
 * Any other failure keeps the last data and retries.
 */
export function useDisplayScreen(): ScreenView {
  const fixed = linkToken();
  const [token, setToken] = useState<string | null>(() => fixed ?? store.read());
  const [reset, setReset] = useState(false);
  const [registerFailed, setRegisterFailed] = useState(false);
  const failures = useRef(0);

  const query = useQuery({
    queryKey: displayStateKey(token ?? ""),
    enabled: Boolean(token),
    queryFn: ({ signal }) => displayScreenApi.state(token as string, signal),
    retry: false,
    refetchOnWindowFocus: false,
    refetchIntervalInBackground: true,
    refetchInterval: (q) => (isGone(q.state.error) ? false : nextPoll(q.state.data, q.state.status === "error")),
  });
  const gone = query.isError && isGone(query.error);

  // Register when there is no secret. Code screens only: a link screen's secret is fixed by its address.
  useEffect(() => {
    if (token || fixed) return;
    let active = true; let timer: number | undefined;
    const attempt = () => {
      registerOnce().then((registration) => {
        if (!active) return;
        store.write(registration.token);
        setRegisterFailed(false);
        setToken(registration.token);
      }, () => { if (active) { setRegisterFailed(true); timer = window.setTimeout(attempt, RETRY_MS); } });
    };
    // After a reset, wait a beat so a server that keeps refusing is not hammered.
    timer = reset ? window.setTimeout(attempt, RETRY_MS) : (attempt(), undefined);
    return () => { active = false; window.clearTimeout(timer); };
  }, [token, fixed, reset]);

  // A 404 on a code screen: drop the secret; the effect above registers again.
  useEffect(() => {
    if (!gone || fixed) return;
    store.write(null);
    setReset(true);
    setToken(null);
  }, [gone, fixed]);

  // Count failures in a row; the first good answer after a long outage reloads the page.
  useEffect(() => { if (query.errorUpdatedAt && !gone) failures.current += 1; }, [query.errorUpdatedAt, gone]);
  useEffect(() => {
    if (!query.dataUpdatedAt) return;
    if (failures.current >= RELOAD_AFTER_FAILURES) { window.location.reload(); return; }
    failures.current = 0;
    setReset(false);
  }, [query.dataUpdatedAt]);

  if (gone && fixed) return { state: null, reconnecting: false, reset: false, linkRevoked: true, updatedAt: null };
  const state = token && !gone ? query.data ?? null : null;
  return { state, reconnecting: (query.isError && !gone) || registerFailed, reset: reset && !state,
    linkRevoked: false, updatedAt: state ? query.dataUpdatedAt : null };
}

/** Panels that have something to show right now, in the staff-chosen order. */
export function availablePanels(state: DisplayState | null): DisplayPanel[] {
  if (!state || state.state !== "paired") return [];
  return state.config.panels.filter((panel) => {
    if (panel === "here_now") return state.here_now !== null;
    if (panel === "calendar") return state.calendar !== null;
    if (panel === "machines") return state.machines !== null && state.machines.items.length > 0;
    if (panel === "public_stats") return state.public_stats !== null && state.public_stats.metrics.length > 0;
    if (panel === "opening_hours") return state.opening_hours !== null;
    if (panel === "inventory_highlights") return Boolean(state.inventory_highlights?.items.length);
    if (panel === "sponsors") return Boolean(state.sponsors?.sponsors.length);
    return Boolean(state.announcement);
  });
}

/** Index of the panel on screen; advances every `seconds`, clamped when the list shrinks. */
export function useRotation(count: number, seconds: number, paused = false): number {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (count <= 1 || paused) return;
    const id = window.setInterval(() => setIndex((old) => (old + 1) % count), Math.max(5, seconds) * 1000);
    return () => window.clearInterval(id);
  }, [count, seconds, paused]);
  return count ? index % count : 0;
}

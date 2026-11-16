export class SessionNavigationInterrupted extends Error {
  constructor() { super("Session transition requires a fresh document."); this.name = "SessionNavigationInterrupted"; }
}
export type BrowserIdentity = "unknown" | "anonymous" | "auth_present";
let state: BrowserIdentity = "unknown", revision = 0;
let fence: (() => boolean) | undefined;
const listeners = new Set<() => void>();
let channel: BroadcastChannel | undefined;
export const browserIdentity = () => state;
export const subscribeBrowserIdentity = (listener: () => void) => { listeners.add(listener); return () => listeners.delete(listener); };
function publish(value: BrowserIdentity) { revision++; state = value; listeners.forEach(listener => listener()); }
export function installSessionTelemetryFence(stopAndReload: () => boolean) {
  fence = stopAndReload;
  try {
    channel = new BroadcastChannel("spaceworks-session-state-v1");
    channel.onmessage = () => { fence?.(); publish("unknown"); window.dispatchEvent(new Event("spaceworks-browser-state-invalidated")); };
  } catch { channel = undefined; }
  const storage = (event: StorageEvent) => { if (event.key === "spaceworks-session-pulse") { fence?.(); publish("unknown"); window.dispatchEvent(new Event("spaceworks-browser-state-invalidated")); } };
  window.addEventListener("storage", storage);
  const visibility = () => { if (document.visibilityState === "visible") { fence?.(); publish("unknown"); window.dispatchEvent(new Event("spaceworks-browser-state-invalidated")); } };
  document.addEventListener("visibilitychange", visibility);
  return () => { window.removeEventListener("storage", storage); document.removeEventListener("visibilitychange", visibility); channel?.close(); fence = undefined; };
}
/** Call synchronously before token/owner changes and before notifying subscribers. */
export function beforeSessionTransition(): boolean {
  const reloading = fence?.() ?? false;
  publish("auth_present");
  try { channel?.postMessage("changed"); } catch { /* fall through to storage signal */ }
  try { localStorage.setItem("spaceworks-session-pulse", crypto.randomUUID()); } catch { /* other tabs recheck on visibility */ }
  return reloading;
}
export function markAuthPresent() { fence?.(); publish("auth_present"); }
export function markSessionUnknown() {
  fence?.(); publish("unknown");
  try { channel?.postMessage("changed"); } catch { /* fallback below */ }
  try { localStorage.setItem("spaceworks-session-pulse", crypto.randomUUID()); } catch { /* visibility rechecks */ }
}
/** Only an explicit server result admits telemetry. Transport and parse failures stay unknown. */
export async function resolveBrowserIdentity(url: string): Promise<BrowserIdentity> {
  publish("unknown");
  const atStart = revision;
  try {
    const response = await fetch(url, { credentials: "include", cache: "no-store", headers: { Accept: "application/json" } });
    if (!response.ok) return state;
    const data: unknown = await response.json();
    if (!data || typeof data !== "object" || !("state" in data)) return state;
    const value = (data as { state: unknown }).state;
    if (atStart === revision && (value === "anonymous" || value === "auth_present")) {
      if (value === "auth_present") fence?.();
      publish(value);
    }
  } catch { /* unknown */ }
  return state;
}









import { beforeSessionTransition, SessionNavigationInterrupted } from "../telemetry/sessionFence";
import { configuredApiUrl } from "../runtimeConfig";

type WorkerReply = { ok?: boolean; ticket?: string; owner_epoch?: string; makerspace_id?: number };
function request(worker: ServiceWorker, data: object): Promise<WorkerReply> {
  return new Promise((resolve, reject) => {
    const channel = new MessageChannel();
    const timer = window.setTimeout(() => { channel.port1.close(); reject(new Error("Notification safety check timed out")); }, 5000); // i18n-ignore: internal worker ACK failure; callers catch it and isolate the worker, never rendered.
    channel.port1.onmessage = event => { clearTimeout(timer); channel.port1.close(); const result = event.data as WorkerReply; if (result?.ok) resolve(result); else reject(new Error("Notification safety check failed")); }; // i18n-ignore: internal worker ACK failure; callers catch it and isolate the worker, never rendered.
    worker.postMessage(data, [channel.port2]);
  });
}
async function clearDormantEpoch() {
  if (!("indexedDB" in window)) return;
  await new Promise<void>((resolve, reject) => {
    const open = indexedDB.open("spaceworks-firebase-alerts", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("state");
    open.onerror = () => reject(open.error);
    open.onsuccess = () => { const db = open.result, tx = db.transaction("state", "readwrite"); tx.objectStore("state").delete("epoch"); tx.oncomplete = () => { db.close(); resolve(); }; tx.onerror = () => { db.close(); reject(tx.error); }; };
  });
}
const budgetMs = 5000;
async function bounded<T>(work: (signal: AbortSignal) => Promise<T>, fallback: T): Promise<T> {
  const abort = new AbortController();
  let timer = 0;
  try {
    return await Promise.race([work(abort.signal), new Promise<T>(resolve => { timer = window.setTimeout(() => { abort.abort(); resolve(fallback); }, budgetMs); })]);
  } catch { abort.abort(); return fallback; } finally { window.clearTimeout(timer); }
}
function isFirebaseWorker(registration: ServiceWorkerRegistration): boolean {
  if (registration.scope !== new URL("/firebase-alerts/", location.origin).href) return false;
  const scripts = [registration.active, registration.waiting, registration.installing].filter(Boolean);
  return scripts.length > 0 && scripts.every(worker => worker!.scriptURL === new URL("/firebase-alerts-sw.js", location.origin).href);
}
async function findWorker() {
  if (!("serviceWorker" in navigator)) return null;
  const registration = await navigator.serviceWorker.getRegistration("/firebase-alerts/").catch(() => undefined);
  if (!registration || !isFirebaseWorker(registration)) { await clearDormantEpoch().catch(() => undefined); return null; }
  if (!registration.active) { await isolate(registration); return null; }
  return registration;
}
async function isolate(registration: ServiceWorkerRegistration) {
  try { const subscription = await registration.pushManager.getSubscription(); await subscription?.unsubscribe(); } catch { /* optional worker may be broken */ }
  await registration.unregister().catch(() => false);
  await clearDormantEpoch().catch(() => undefined);
}
let pendingFreeze: Promise<void> = Promise.resolve();
async function freezeWorker() {
  const registration = await findWorker(); if (!registration?.active) return;
  try { await request(registration.active, { kind: "freeze" }); } catch { await isolate(registration); }
}
/** Identity loss may start asynchronously; the next identity gain waits for its ACK. */
export function queuePrivacyFreeze() { pendingFreeze = pendingFreeze.catch(() => undefined).then(() => bounded(async () => { await freezeWorker(); }, undefined)); void pendingFreeze.catch(() => undefined); }
/** Freeze before cookie-changing requests. A failed optional worker is retired, not an auth loop. */
export async function freezeBeforeAuthMutation(path: string, method: string) {
  // Authenticated step-up confirms the existing actor and does not mutate refresh cookies.
  if (/^\/auth\/reauth(?:\/|$)/.test(path)) return;
  if (["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase()) || !/^\/(?:auth(?:\/|$)|passkeys?(?:\/|$))/.test(path)) return;
  if (beforeSessionTransition()) throw new SessionNavigationInterrupted();
  await bounded(async () => { try { await pendingFreeze; } catch { /* retry */ } await freezeWorker(); }, undefined);
}
export type SuspendedPush = { worker: ServiceWorker; ticket: string; ownerEpoch: string };
/** The worker clears the persistent epoch before returning a short-lived same-client ticket. */
export async function suspendPushForRefresh(): Promise<SuspendedPush | null> {
  return bounded(async () => {
  await pendingFreeze;
  const registration = await findWorker(); if (!registration?.active) return null;
  try {
    const reply = await request(registration.active, { kind: "suspend" });
    if (typeof reply.ticket !== "string" || typeof reply.owner_epoch !== "string") return null;
    return { worker: registration.active, ticket: reply.ticket, ownerEpoch: reply.owner_epoch };
  } catch { await isolate(registration); return null; }
  }, null);
}
/** Server checks the new actor against the global owner; restore only the worker-held exact version. */
export async function resumePushAfterRefresh(suspended: SuspendedPush | null, access: string) {
  if (!suspended) return;
  const base = configuredApiUrl().replace(/\/api$/, "/api/v1");
  await bounded(async signal => {
  try {
    const response = await fetch(`${base}/notifications/browser-firebase/may-resume`, { signal, method: "POST", credentials: "include", headers: { "Content-Type": "application/json", Authorization: `Bearer ${access}` }, body: JSON.stringify({ owner_epoch: suspended.ownerEpoch }) });
    if (!response.ok || (await response.json()).may_resume !== true) return;
    if (!signal.aborted) await request(suspended.worker, { kind: "resume", ticket: suspended.ticket });
  } catch { /* remains frozen */ }
  }, undefined);
}







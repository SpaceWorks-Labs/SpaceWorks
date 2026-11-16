/// <reference lib="webworker" />
import { cachePolicy } from "./swPolicy";
import { listQueues, pruneKioskQueues } from "./features/kiosk/offlineQueueStore";
import { replayQueue } from "./features/kiosk/kioskReplayClient";
import { pruneExpiredOfflineStates } from "./features/staff/eventCheckInOfflineStore";

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: { url: string; revision: string }[] };
const manifest = self.__WB_MANIFEST;
const paths = new Set(manifest.map((entry) => entry.url));
const CACHE_PREFIX = "spaceworks-app-shell-";
// Hashed preview vendors: cache-first, kept at most 30 days and 8 entries.
const PREVIEW_CACHE = "spaceworks-preview-runtime-v1";
const PREVIEW_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const PREVIEW_MAX_ENTRIES = 8;
const CACHED_AT = "x-spaceworks-cached-at";

async function previewResponse(request: Request) {
  const cache = await caches.open(PREVIEW_CACHE);
  const path = new URL(request.url).pathname;
  const cached = await cache.match(path);
  if (cached && Date.now() - Number(cached.headers.get(CACHED_AT)) < PREVIEW_MAX_AGE_MS) return cached;
  const response = await fetch(request);
  if (!response.ok || response.redirected) return response;
  const headers = new Headers(response.headers);
  headers.set(CACHED_AT, String(Date.now()));
  await cache.put(path, new Response(await response.clone().blob(), { status: response.status, statusText: response.statusText, headers }));
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - PREVIEW_MAX_ENTRIES)).map((key) => cache.delete(key)));
  return response;
}
// Injected revisions produce a version-specific cache without hardcoded chunks.
const cacheName = async () => CACHE_PREFIX + [...new Uint8Array(await crypto.subtle.digest(
  "SHA-256", new TextEncoder().encode(JSON.stringify(manifest)),
))].map((byte) => byte.toString(16).padStart(2, "0")).join("");

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(await cacheName());
    await Promise.all(manifest.map(async ({ url, revision }) => {
      const response = await fetch(new Request(new URL(url, self.location.origin), { cache: "reload", credentials: "omit" }));
      if (!response.ok || response.redirected) throw new Error("App shell precache failed.");
      const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", await response.clone().arrayBuffer()))]
        .map((byte) => byte.toString(16).padStart(2, "0")).join("");
      if (digest !== revision) throw new Error("Deployment changed during app shell installation.");
      await cache.put(url, response);
    }));
  })());
  // No skipWaiting: the installed update waits until all old clients (and their
  // waitUntil replay events) finish. It cannot replace an active replay worker.
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const current = await cacheName();
    await Promise.all((await caches.keys()).filter((name) =>
      (name.startsWith(CACHE_PREFIX) || name === "spaceworks-static-v1") && name !== current,
    ).map((name) => caches.delete(name)));
    await Promise.allSettled([pruneKioskQueues(), pruneExpiredOfflineStates()]);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const policy = cachePolicy(event.request, self.location.origin, paths);
  if (policy === "network") return;
  if (policy === "preview") {
    event.respondWith(previewResponse(event.request).catch(() => Response.error()));
    return;
  }
  event.respondWith((async () => {
    const cache = await caches.open(await cacheName());
    if (policy === "kiosk") {
      // Navigation responses can contain deployment-specific data: NEVER store
      // them. Only the build's public index.html can be an offline shell.
      try {
        const response = await fetch(event.request, { signal: AbortSignal.timeout(5000) });
        if (response.status >= 500) throw new Error("Navigation server unavailable.");
        return response;
      }
      catch { return await cache.match("/index.html") ?? Response.error(); }
    }
    return await cache.match(new URL(event.request.url).pathname) ?? fetch(event.request);
  })());
});

type SyncEvent = ExtendableEvent & { tag: string };
self.addEventListener("sync", ((event: SyncEvent) => {
  if (event.tag !== "spaceworks-kiosk-replay") return;
  event.waitUntil((async () => {
    for (const queue of await listQueues()) await replayQueue(queue.scope);
  })());
}) as EventListener);

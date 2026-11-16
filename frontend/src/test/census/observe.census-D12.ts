import { MutationCache, QueryCache, Query } from "@tanstack/react-query";
import { AsyncLocalStorage } from "node:async_hooks";
import { vi } from "vitest";
import * as React from "react";
import * as apiErrors from "../../lib/api/errors";
import * as kioskApi from "../../features/kiosk/kioskApi";
import * as eventStation from "../../features/staff/eventCheckInOfflineApi";
import * as requests from "../../lib/api/requests";

// Capture once, so a failed hook can never wrap a spy with another spy.
const buildQuery = QueryCache.prototype.build;
const buildMutation = MutationCache.prototype.build;
const fetchQuery = Query.prototype.fetch;
const makeApiError = apiErrors.apiError;
const unlockKiosk = kioskApi.startKioskSession;
const unlockEvent = eventStation.startStationSession;
const publicRequest = requests.publicV1Request;
type Fiber = { type?: string | { name?: string; displayName?: string; render?: { name?: string } };
  child?: Fiber; sibling?: Fiber; return?: Fiber; stateNode?: { current?: Fiber } };
function fiberName(fiber: Fiber) {
  const type = fiber.type;
  return typeof type === "string" ? type : type?.displayName ?? type?.name ?? type?.render?.name ?? "";
}

/** ProgrammeAccess owns a nested QueryClient. Observe every REAL cache without replacing it. */
export function observeQueryCaches() {
  const caches = new Set<QueryCache>();
  const mutationCaches = new Set<MutationCache>();
  const rendered = new Set<string>();
  const errors: unknown[] = [];
  const localResults: unknown[] = [];
  // The scope names the render owners of the Query whose fetch is running. AsyncLocalStorage also carries it
  // into every later continuation of that fetch (React renders and effects scheduled when it resolves), so a
  // scope only counts while its own Query is still fetching; a stale one is "no known owner".
  const requestScope = new AsyncLocalStorage<{ owner: Set<string>; query: Query }>();
  const owners = new WeakMap<object, Set<string>>();
  // Username availability deliberately stores its returned data in React state.
  // Preserve the exact API promise and fulfilled value, including queryFns
  // which transform that value before caching their projection.
  const publicSpy = vi.spyOn(requests, "publicV1Request").mockImplementation(((...args: Parameters<typeof publicRequest>) => {
    const promise = publicRequest(...args);
    // Some queryFns transform this result (username suggestions), and programme
    // parsers return validated projections. Observe the real fulfilled value too.
    void promise.then(value => { localResults.push(value); }, () => undefined);
    return promise;
  }) as typeof publicRequest);
  // Some screens deliberately hold request state in React useState. Observe the
  // real parser's result before their catch converts it to display copy; keep its
  // arguments, error identity, status and body unchanged.
  const errorSpy = vi.spyOn(apiErrors, "apiError").mockImplementation((...args) => {
    const error = makeApiError(...args); errors.push(error); return error;
  });
  // Station transports construct errors directly instead of using apiError.
  // Delegate unchanged and rethrow the SAME caught object, including missing codes.
  const kioskSpy = vi.spyOn(kioskApi, "startKioskSession").mockImplementation((...args) => unlockKiosk(...args)
    .catch(error => { errors.push(error); throw error; }));
  const eventSpy = vi.spyOn(eventStation, "startStationSession").mockImplementation((...args) => unlockEvent(...args)
    .catch(error => { errors.push(error); throw error; }));
  const recordRender = () => {
    // A useQuery can fetch before commit. Its first request is already a leaf
    // request, even though the committed tree still contains only its parent.
    const internals = (React as unknown as { __CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE:
      { A: { getOwner?: () => Fiber | null } | null } }).__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
    if (!internals) throw new Error("D12 requires the React 19 development render probe.");
    const current = new Set<string>();
    for (let fiber = internals.A?.getOwner?.(); fiber; fiber = fiber.return) {
      current.add(fiberName(fiber)); rendered.add(fiberName(fiber));
    }
    return current;
  };
  const original = buildQuery;
  const spy = vi.spyOn(QueryCache.prototype, "build");
  spy.mockImplementation(function (this: QueryCache, ...args: Parameters<typeof original>) {
    caches.add(this);
    const current = recordRender();
    const query = original.apply(this, args);
    // Imperative cache reads have no render owner; retain the owning observer.
    if (current.size) owners.set(query, new Set([...owners.get(query) ?? [], ...current]));
    return query;
  } as typeof original);
  // Delegate the real fetch unchanged, retaining its exact promise/result/error.
  // Async context follows awaits through the API client to the fetch boundary.
  const fetchSpy = vi.spyOn(Query.prototype, "fetch").mockImplementation(function (this: Query, ...args: Parameters<typeof fetchQuery>) {
    const owner = owners.get(this);
    // The first optimistic or imperative fetch can precede a render owner. Its query identity still exists.
    return requestScope.run({ owner: owner ?? new Set<string>(), query: this }, () => fetchQuery.apply(this, args));
  } as typeof fetchQuery);
  const originalMutation = buildMutation;
  const mutationSpy = vi.spyOn(MutationCache.prototype, "build");
  mutationSpy.mockImplementation(function (this: MutationCache, ...args: Parameters<typeof originalMutation>) {
    mutationCaches.add(this);
    recordRender();
    return originalMutation.apply(this, args);
  } as typeof originalMutation);
  return { rendered, errors, localResults, requestOwner: () => {
    const scope = requestScope.getStore();
    return scope?.query.state.fetchStatus === "fetching" && scope.owner.size ? scope.owner : undefined;
  }, requestOperation: () => {
    const scope = requestScope.getStore();
    return scope?.query.state.fetchStatus === "fetching" ? scope.query.queryHash : undefined;
  }, queries: () => [...caches].flatMap(cache => cache.getAll()),
    mutations: () => [...mutationCaches].flatMap(cache => cache.getAll()),
    clear() { for (const cache of caches) cache.clear(); for (const cache of mutationCaches) cache.clear(); },
    restore() { spy.mockRestore(); fetchSpy.mockRestore(); mutationSpy.mockRestore(); errorSpy.mockRestore(); publicSpy.mockRestore(); kioskSpy.mockRestore(); eventSpy.mockRestore(); requestScope.disable(); } };
}
/** Read-only React 19 observation: a parent error must never count as mounting a gated child. */
export function mountedScreens(container: HTMLElement) {
  const key = Object.keys(container).find(name => name.startsWith("__reactContainer$"));
  if (!key) throw new Error("D12 cannot observe the mounted React route; update its React 19 probe.");
  const host = (container as unknown as Record<string, Fiber>)[key];
  const names = new Set<string>();
  const seen = new Set<Fiber>();
  const visit = (fiber: Fiber | undefined) => {
    if (!fiber || seen.has(fiber)) return;
    seen.add(fiber);
    names.add(fiberName(fiber));
    visit(fiber.child); visit(fiber.sibling);
  };
  visit(host.stateNode?.current ?? host);
  return names;
}

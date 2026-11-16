import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { UnsubscribePage } from "../../features/notifications/UnsubscribePage";
import { StructuredApiError } from "../../lib/api/errors";
import { installFetch, REFUSALS, type Exchange } from "./fetch.census-D12";
import { observeQueryCaches } from "./observe.census-D12";
import { assertScreenRetries, retryProof } from "./retries.census-D12";
import { runRetryAttempt } from "./attempts.census-D12";
import { routeInventory, type RouteCase } from "./source.census-D12";

let client: QueryClient;
let observed: ReturnType<typeof observeQueryCaches>;
let network: ReturnType<typeof installFetch>;
afterEach(async () => {
  cleanup(); await client?.cancelQueries(); client?.clear(); observed?.restore(); observed?.clear();
  network?.dispose(); vi.unstubAllGlobals();
});
const row = { id: "retry-proof", screen: "CensusRetryPage", mode: "single", path: "/", pattern: "/", file: "", line: 1 } as RouteCase;
async function load(page: number) {
  const response = await fetch(`/api/v1/admin/makerspace/1/payments?page=${page}`);
  const body = await response.json();
  if (!response.ok) throw new StructuredApiError(response.status, body);
  return body;
}
function CensusRetryPage({ broken }: { broken: boolean }) {
  const first = useQuery({ queryKey: ["payments", 1], queryFn: () => load(1) });
  const second = useQuery({ queryKey: ["payments", 2], queryFn: () => load(2) });
  return <main><button onClick={() => void first.refetch()}>Retry first</button>
    <button onClick={() => void (broken ? first : second).refetch()}>Retry second</button></main>;
}
async function start(broken: boolean) {
  observed = observeQueryCaches();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  network = installFetch("error", false, row, () => true, observed.requestOwner, observed.requestOperation);
  function App() { return <CensusRetryPage broken={broken} />; }
  render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
  await waitFor(() => expect(client.getQueryCache().getAll().map(query => query.state.status)).toEqual(["error", "error"]));
  expect(network.own()).toHaveLength(2);
  for (const query of client.getQueryCache().getAll()) {
    const error = query.state.error as StructuredApiError;
    expect(error).toBeInstanceOf(StructuredApiError);
    expect({ status: error.status, code: error.code }).toEqual({ status: 503, code: "service_unavailable" });
  }
}
async function click(name: string) {
  const before = network.exchanges.length;
  runRetryAttempt(name, () => fireEvent.click(screen.getByRole("button", { name })));
  await waitFor(() => expect(network.exchanges.length).toBe(before + 1));
  await waitFor(() => expect(client.getQueryCache().getAll().map(query => query.state.fetchStatus)).toEqual(["idle", "idle"]));
  return network.exchanges.slice(before);
}

it("rejects two failed queries whose two controls both refetch only the first query", async () => {
  await start(true);
  const proof = retryProof(network.exchanges);
  proof.attempt("Retry first", await click("Retry first"));
  proof.attempt("Retry second", await click("Retry second"));
  expect(() => proof.complete()).toThrow("Failed operations without their own retry proof");
});
it("rejects a retry for which only outside/support traffic increases", async () => {
  await start(false);
  const proof = retryProof(network.exchanges);
  const before = network.exchanges.length;
  const outside = installFetch("error", false, row, () => true, () => new Set(["TenantProvider"]));
  try {
    const response = await runRetryAttempt("Retry first", () => fetch("/api/v1/admin/makerspace/1/payments?page=1"));
    expect(response.status).toBe(503); expect(await response.json()).toEqual(REFUSALS.error);
    expect(outside.own()).toEqual([]);
    const fresh = [...network.exchanges.slice(before), ...outside.exchanges];
    expect(() => proof.attempt("Retry first", fresh)).toThrow("No new screen-owned attempt");
    expect(() => proof.attempt("Retry first", fresh.map(exchange => ({ ...exchange, support: true })))).toThrow("No new screen-owned attempt");
  } finally { outside.dispose(); }
});
it("proves both independent queries including their different query parameters", async () => {
  await start(false);
  const proof = retryProof(network.exchanges);
  const first = await click("Retry first"), second = await click("Retry second");
  expect(first.map(exchange => exchange.target)).toEqual(["/api/v1/admin/makerspace/1/payments?page=1"]);
  expect(second.map(exchange => exchange.target)).toEqual(["/api/v1/admin/makerspace/1/payments?page=2"]);
  proof.attempt("Retry first", first); proof.attempt("Retry second", second); proof.complete();
  expect(() => proof.attempt("Retry first", first.map(exchange => ({ ...exchange, attempt: "earlier gesture" }))))
    .toThrow("No new screen-owned attempt");
  const wrong: Exchange[] = second.map(exchange => ({ ...exchange, body: { code: "permission_denied" } }));
  expect(() => proof.attempt("Retry second", wrong)).toThrow();
  expect(() => proof.attempt("Retry first", second.map(exchange => ({ ...exchange, attempt: "Retry first" })))).toThrow("Retry binding changed");
});

it("reacquires the same retry control after React replaces its loading branch", async () => {
  observed = observeQueryCaches();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const route = { ...row, screen: "RemountingRetryPage" };
  network = installFetch("error", false, route, () => true, observed.requestOwner, observed.requestOperation);
  function RemountingRetryPage() {
    const query = useQuery({ queryKey: ["payments", 1], queryFn: () => load(1) });
    return <main>{query.isFetching ? <p role="status">Loading</p>
      : <button onClick={() => void query.refetch()}>Retry</button>}</main>;
  }
  function App() { return <RemountingRetryPage />; }
  render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
  const settled = async () => {
    await waitFor(() => {
      const state = client.getQueryState(["payments", 1])!;
      expect(state.fetchStatus).toBe("idle");
      const error = state.error as StructuredApiError;
      expect({ status: error.status, code: error.code }).toEqual({ status: 503, code: "service_unavailable" });
    });
  };
  await settled();
  await assertScreenRetries(route, network, settled);
  expect(network.own()).toHaveLength(3);
});

it("keeps the query identity when its first fetch precedes a render owner", async () => {
  observed = observeQueryCaches();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const route = { ...row, screen: "ImperativeRetryPage" };
  network = installFetch("error", false, route, () => true, observed.requestOwner, observed.requestOperation);
  await expect(client.fetchQuery({ queryKey: ["payments", 1], queryFn: () => load(1) }))
    .rejects.toMatchObject({ status: 503, code: "service_unavailable" });
  expect(network.own().map(exchange => exchange.operation)).toEqual(['["payments",1]']);
  function ImperativeRetryPage() {
    const query = useQuery({ queryKey: ["payments", 1], queryFn: () => load(1), retryOnMount: false, refetchOnMount: false });
    return <main><button onClick={() => void query.refetch()}>Retry</button></main>;
  }
  function App() { return <ImperativeRetryPage />; }
  render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
  const proof = retryProof(network.exchanges);
  runRetryAttempt("Retry", () => fireEvent.click(screen.getByRole("button", { name: "Retry" })));
  await waitFor(() => expect(network.own()).toHaveLength(2));
  await waitFor(() => expect(client.getQueryState(["payments", 1])?.fetchStatus).toBe("idle"));
  proof.attempt("Retry", network.exchanges.slice(1));
  proof.complete();
});

it("reacquires Retry when a failed command changes its original action label", async () => {
  observed = observeQueryCaches();
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const route = routeInventory().find(item => item.screen === "UnsubscribePage" && item.mode === "central")!;
  network = installFetch("error", false, route, () => true, observed.requestOwner, observed.requestOperation);
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route.path]}><Routes>
    <Route path="/unsubscribe/:token" element={<UnsubscribePage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Unsubscribe" }));
  const settled = async () => {
    await waitFor(() => {
      const mutations = client.getMutationCache().getAll();
      const mutation = mutations[mutations.length - 1]!;
      expect(mutation.state.status).toBe("error");
      expect(mutation.state.error).toMatchObject({ status: 503, code: "service_unavailable" });
    });
  };
  await settled();
  await assertScreenRetries(route, network, settled);
  expect(network.own()).toHaveLength(3);
});

it("includes a failed query whose observer notification has not committed yet", async () => {
  observed = observeQueryCaches();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const route = { ...row, screen: "LateRetryPage" };
  network = installFetch("error", false, route, () => true, observed.requestOwner, observed.requestOperation);
  await expect(client.fetchQuery({ queryKey: ["payments", 1], queryFn: () => load(1) }))
    .rejects.toMatchObject({ status: 503, code: "service_unavailable" });
  client.setQueryData(["payments", 2], []);
  function LateRetryPage() {
    const first = useQuery({ queryKey: ["payments", 1], queryFn: () => load(1), enabled: false });
    const second = useQuery({ queryKey: ["payments", 2], queryFn: () => load(2), enabled: false });
    return <main>{[first, second].map((query, index) => query.error
      ? <button key={index} onClick={() => void query.refetch()}>Retry</button> : null)}</main>;
  }
  function App() { return <LateRetryPage />; }
  render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
  await expect(client.fetchQuery({ queryKey: ["payments", 2], queryFn: () => load(2) }))
    .rejects.toMatchObject({ status: 503, code: "service_unavailable" });
  // Query state is already failed; its observer still shows the previous successful snapshot.
  expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1);
  const settled = async () => {
    await waitFor(() => {
      for (const page of [1, 2]) {
        const state = client.getQueryState(["payments", page])!;
        expect(state.fetchStatus).toBe("idle");
        expect(state.error).toMatchObject({ status: 503, code: "service_unavailable" });
      }
    });
  };
  await assertScreenRetries(route, network, settled);
  expect(network.own()).toHaveLength(6);
});

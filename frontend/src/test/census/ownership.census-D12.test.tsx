import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { observeQueryCaches } from "./observe.census-D12";

let observed: ReturnType<typeof observeQueryCaches> | undefined;
let client: QueryClient | undefined;
afterEach(async () => {
  cleanup();
  await client?.cancelQueries(); client?.clear();
  observed?.restore(); observed?.clear();
  vi.unstubAllGlobals();
});

it("retains query ownership across awaits and a parent refetch after the child mounts", async () => {
  observed = observeQueryCaches();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const requests: { path: string; owners: Set<string> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    requests.push({ path, owners: new Set(observed!.requestOwner()) });
    return new Response("[]", { headers: { "Content-Type": "application/json" } });
  }));
  const load = async (path: string) => {
    await Promise.resolve();
    return (await fetch(path)).json();
  };
  function CensusOwnedLeaf() {
    useQuery({ queryKey: ["leaf"], queryFn: () => load("/leaf") });
    return <p>Leaf</p>;
  }
  function CensusOwnedParent() {
    useQuery({ queryKey: ["parent"], queryFn: () => load("/parent") });
    return <CensusOwnedLeaf />;
  }
  render(<QueryClientProvider client={client}><CensusOwnedParent /></QueryClientProvider>);
  await waitFor(() => expect(requests).toHaveLength(2));
  await waitFor(() => {
    expect(client!.getQueryState(["parent"])?.status).toBe("success");
    expect(client!.getQueryState(["leaf"])?.status).toBe("success");
  });
  await client.refetchQueries({ queryKey: ["parent"], exact: true });
  expect(requests.slice(0, 2).map(item => item.path).sort()).toEqual(["/leaf", "/parent"]);
  expect(requests).toHaveLength(3);
  expect(requests[2].path).toBe("/parent");
  for (const request of requests.filter(item => item.path === "/parent")) {
    expect(request.owners.has("CensusOwnedParent")).toBe(true);
    expect(request.owners.has("CensusOwnedLeaf")).toBe(false);
  }
  const leaf = requests.find(item => item.path === "/leaf")!;
  expect(leaf.owners.has("CensusOwnedParent")).toBe(true);
  expect(leaf.owners.has("CensusOwnedLeaf")).toBe(true);
});

it("preserves the exact thrown error, HTTP status and refusal code in the real query cache", async () => {
  observed = observeQueryCaches();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const refusal = new StructuredApiError(403, { code: "permission_denied", detail: "Census access denied." });
  function CensusRefusedLeaf() {
    useQuery({ queryKey: ["refused-leaf"], queryFn: async () => { await Promise.resolve(); throw refusal; } });
    return <p>Refused leaf</p>;
  }
  render(<QueryClientProvider client={client}><CensusRefusedLeaf /></QueryClientProvider>);
  await waitFor(() => expect(client!.getQueryState(["refused-leaf"])?.status).toBe("error"));
  const error = client.getQueryState(["refused-leaf"])!.error;
  expect(error).toBe(refusal);
  expect({ status: (error as StructuredApiError).status, code: (error as StructuredApiError).code })
    .toEqual({ status: 403, code: "permission_denied" });
});

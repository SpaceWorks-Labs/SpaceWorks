import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useCachedQueryData } from "./useCachedQueryData";

function Owner({ fetcher }: { fetcher: () => Promise<{ n: number }> }) {
  const query = useQuery({ queryKey: ["dashboard", 4], queryFn: fetcher });
  return <p>owner {query.data?.n ?? "-"} {query.isError ? "error" : "ok"}</p>;
}
function Reader() {
  const data = useCachedQueryData<{ n: number }>(["dashboard", 4]);
  return <p>reader {data?.n ?? "-"}</p>;
}

describe("useCachedQueryData", () => {
  it("mirrors the owner's cache and never breaks the owner's refetch", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let n = 0;
    const fetcher = vi.fn(async () => ({ n: ++n }));
    render(<QueryClientProvider client={client}><Owner fetcher={fetcher} /><Reader /></QueryClientProvider>);
    await waitFor(() => expect(screen.getByText("reader 1")).toBeTruthy());
    await act(async () => { await client.invalidateQueries({ queryKey: ["dashboard", 4] }); });
    await waitFor(() => expect(screen.getByText("reader 2")).toBeTruthy());
    expect(screen.getByText("owner 2 ok")).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not fetch on its own", () => {
    const client = new QueryClient();
    render(<QueryClientProvider client={client}><Reader /></QueryClientProvider>);
    expect(screen.getByText("reader -")).toBeTruthy();
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });
});

import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { clearAccessToken, setAccessToken } from "../../lib/api";
import { connectedChannels } from "./PersonalChannels";
import { useEndpoints } from "./channelsApi";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const token = `header.${btoa(JSON.stringify({ user_id: 7, exp: 9_999_999_999 }))}.signature`;
const endpoint = (id: number, channel: string, valid = false) => ({ id, channel, effective_valid: valid });
function endpoints(member: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderHook(() => useEndpoints(7, member), {
    wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
}
afterEach(() => { clearAccessToken(); vi.unstubAllGlobals(); });

it.each([false, true])("loads every connection page for member=%s", async member => {
  setAccessToken(token);
  const fetcher = vi.fn(async (url: string) => {
    const page = new URL(url).searchParams.get("page");
    if (page === "2") return response({ count: 50, next: "/api/v1/integrations/makerspace/7/personal/endpoints?page=3",
      previous: "?page=1", results: Array.from({ length: 24 }, (_, i) => endpoint(25 + i, "discord")) });
    if (page === "3") return response({ count: 50, next: null, previous: "?page=2",
      results: [endpoint(49, "telegram", true), endpoint(50, "slack", true)] });
    return response({ count: 50, next: "http://backend.internal/api/v1/integrations/makerspace/7/personal/endpoints?page=2",
      previous: null, results: Array.from({ length: 24 }, (_, i) => endpoint(1 + i, "discord")) });
  });
  vi.stubGlobal("fetch", fetcher);
  const { result } = endpoints(member);
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.results).toHaveLength(50);
  expect(result.current.data?.next).toBeNull();
  expect(connectedChannels(result.current.data?.results)).toEqual(new Set(["telegram", "slack"]));
  expect(fetcher).toHaveBeenCalledTimes(3);
  const urls = fetcher.mock.calls.map(([url]) => new URL(url));
  expect(new Set(urls.map(url => url.origin)).size).toBe(1);
  expect(urls.map(url => url.search)).toEqual(["", "?page=2", "?page=3"]);
});

it("does not expose a partial connection list when a later page fails", async () => {
  setAccessToken(token);
  const fetcher = vi.fn(async (url: string) => url.includes("page=2") ? response({}, 500)
    : response({ count: 25, next: "?page=2", previous: null, results: [endpoint(1, "discord")] }));
  vi.stubGlobal("fetch", fetcher);
  const { result } = endpoints(true);
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(result.current.data).toBeUndefined();
  expect(result.current.error).toMatchObject({ status: 500 });
});

import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { clearAccessToken, getAccessToken, setAccessToken } from "../../lib/api";
import { StructuredApiError } from "../../lib/api";
import { usePublicProfile, usePublicProfileActivity, usePublicProfileEvents,
  usePublicProfileProjects, usePublicProfileGithub } from "./publicProfileApi";

const token = (exp: number) => `header.${btoa(JSON.stringify({ user_id: 7, exp }))}.signature`;
const expired = token(1);
const fresh = token(9_999_999_999);
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function profile() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderHook(() => usePublicProfile("maker"), {
    wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
}

beforeEach(() => { clearAccessToken(); setAccessToken(expired); });
afterEach(() => { clearAccessToken(); vi.unstubAllGlobals(); });

it("refreshes an expired access token and retries the personalized profile", async () => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) return response({ access: fresh });
    const auth = new Headers(options?.headers).get("Authorization");
    return auth === `Bearer ${fresh}` ? response({ handle: "maker", viewer_is_owner: true }) : response({}, 401);
  });
  vi.stubGlobal("fetch", fetcher);
  const { result } = profile();
  await waitFor(() => expect(result.current.data?.viewer_is_owner).toBe(true));
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
  const profileCalls = fetcher.mock.calls.filter(([url]) => url.endsWith("/public/profiles/maker/"));
  expect(profileCalls.map(([, options]) => new Headers(options?.headers).get("Authorization")))
    .toEqual([`Bearer ${expired}`, `Bearer ${fresh}`]);
});

it.each(["refused", "offline", "invalid_refresh"])("falls back to anonymous viewing when refresh is %s", async failure => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) {
      if (failure === "offline") throw new TypeError("Network unavailable");
      return failure === "invalid_refresh" ? response({ access: fresh }) : response({}, 401);
    }
    return new Headers(options?.headers).get("Authorization")
      ? response({}, 401) : response({ handle: "maker", viewer_is_owner: false });
  });
  vi.stubGlobal("fetch", fetcher);
  const { result } = profile();
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.viewer_is_owner).toBe(false);
  expect(fetcher.mock.calls.some(([url, options]) => url.endsWith("/public/profiles/maker/")
    && !new Headers(options?.headers).get("Authorization"))).toBe(true);
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
});


it("retries a verification-only session anonymously without clearing the session", async () => {
  setAccessToken(fresh);
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) =>
    new Headers(options?.headers).get("Authorization")
      ? response({ code: "email_verification_required" }, 403)
      : response({ handle: "maker", viewer_is_owner: false }));
  vi.stubGlobal("fetch", fetcher);
  const { result } = profile();
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.viewer_is_owner).toBe(false);
  expect(getAccessToken()).toBe(fresh);
  expect(fetcher.mock.calls.map(([, options]) => new Headers(options?.headers).get("Authorization")))
    .toEqual([`Bearer ${fresh}`, ""]);
});

const publicReads = [
  { name: "profile", hook: () => usePublicProfile("maker") },
  { name: "activity", hook: () => usePublicProfileActivity("maker", true) },
  { name: "events", hook: () => usePublicProfileEvents("maker", 1, true) },
  { name: "projects", hook: () => usePublicProfileProjects("maker", 1, true) },
  { name: "github", hook: () => usePublicProfileGithub("maker", true) },
];

it.each(publicReads)("$name retries 403 anonymously and accepts the public consent refusal", async ({ name, hook }) => {
  setAccessToken(fresh);
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) =>
    new Headers(options?.headers).get("Authorization") ? response({}, 403) : response({}, 404));
  vi.stubGlobal("fetch", fetcher);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { result } = renderHook(() => hook(), {
    wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  await waitFor(() => expect(name === "github" ? result.current.isSuccess : result.current.isError).toBe(true));
  if (name === "github") expect(result.current.data).toBeNull();
  else expect(result.current.error).toMatchObject({ status: 404 });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("keeps a profile's own 404 authoritative without an anonymous retry", async () => {
  setAccessToken(fresh);
  const fetcher = vi.fn(async () => response({}, 404));
  vi.stubGlobal("fetch", fetcher);
  const { result } = profile();
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(result.current.error).toBeInstanceOf(StructuredApiError);
  expect(result.current.error).toMatchObject({ status: 404 });
  expect(fetcher).toHaveBeenCalledTimes(1);
});

// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: useStaffSession is not in release 0.12.0 (replaced by useConsoleSession).
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useStaffSession } from "./useStaffSession";
import { clearAccessToken, getAccessToken, setAccessToken } from "../../lib/api";
import { setRouteSessionContext } from "../../lib/api/sessionContext";

const mocks = vi.hoisted(() => ({ refresh: vi.fn(), me: vi.fn(), request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(),
  refreshAccessToken: mocks.refresh, fetchMe: mocks.me, staffRequest: mocks.request,
}));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "central", slug: "", makerspaceId: null }) }));
vi.mock("../../lib/useLiveUpdates", () => ({ useLiveUpdates: () => {} }));
vi.mock("./panels/shared", () => ({ useStaffGet: () => ({ data: [], isLoading: false }) }));
const user = { username: "operator.forge", account_kind: "staff", makerspaces: [], role: "inventory_manager", is_superuser: false,
  email_verified: true, must_change_password: true } as const;
function mount(path: string) {
  window.history.replaceState(null, "", path);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[path]}><QueryClientProvider client={client}>{children}</QueryClientProvider></MemoryRouter>;
  return renderHook(() => useStaffSession(false), { wrapper });
}
beforeEach(() => { vi.clearAllMocks(); setRouteSessionContext("member"); mocks.refresh.mockResolvedValue(false); });
afterEach(() => { clearAccessToken("member"); clearAccessToken("staff:forge"); clearAccessToken("platform"); window.history.replaceState(null, "", "/"); });

it("logs in with the route's makerspace and preserves the simultaneously signed-in member", async () => {
  setAccessToken("member-token", "member"); mocks.request.mockResolvedValue({ access: "staff-token", surface: "staff", user });
  const { result } = mount("/m/forge/admin/inventory");
  await waitFor(() => expect(result.current.restoring).toBe(false));
  await act(() => result.current.login.mutateAsync({ username: "operator@example.com", password: "temporary" }));
  expect(mocks.request).toHaveBeenCalledWith("/auth/login", expect.objectContaining({ body: JSON.stringify({
    username: "operator@example.com", password: "temporary", surface: "staff", context: "staff", makerspace: "forge",
  }) }), "staff:forge");
  expect(getAccessToken("member")).toBe("member-token"); expect(getAccessToken("staff:forge")).toBe("staff-token");
  await waitFor(() => expect(result.current.user?.must_change_password).toBe(true));
});

it("keeps staff MFA in its context through challenge completion", async () => {
  const challenge = { mfa_required: true, enrollment_required: false, challenge: "opaque-challenge", expires_in: 300 };
  mocks.request.mockResolvedValue(challenge); setAccessToken("member-token", "member");
  const { result } = mount("/m/forge/admin/inventory");
  await waitFor(() => expect(result.current.restoring).toBe(false));
  await act(() => result.current.login.mutateAsync({ username: "operator", password: "temporary" }));
  expect(result.current.mfaChallenge).toEqual(challenge); expect(result.current.user).toBeNull();
  act(() => result.current.mfaCompleted({ access: "mfa-staff", surface: "staff", user: { ...user, makerspaces: [] } }));
  expect(getAccessToken("staff:forge")).toBe("mfa-staff"); expect(getAccessToken("member")).toBe("member-token");
});

it("restores a helper workspace through member context with delegated surface", async () => {
  mocks.refresh.mockResolvedValue(true); mocks.me.mockResolvedValue({ ...user, account_kind: "member", must_change_password: false });
  const { result } = mount("/admin/assigned-events");
  await waitFor(() => expect(result.current.restoring).toBe(false));
  expect(result.current.delegated).toBe(true);
  expect(mocks.refresh).toHaveBeenCalledWith("member"); expect(mocks.me).toHaveBeenCalledWith("member", "delegated");
  expect(mocks.request).not.toHaveBeenCalledWith("/auth/login", expect.anything(), expect.anything());
});

it("names platform context for the existing React superadmin console", async () => {
  mocks.request.mockResolvedValue({ access: "platform-token", surface: "staff", user: { ...user, account_kind: "platform", is_superuser: true } });
  const { result } = mount("/admin/users");
  await waitFor(() => expect(result.current.restoring).toBe(false));
  await act(() => result.current.login.mutateAsync({ username: "operator", password: "password" }));
  const loginCall = mocks.request.mock.calls.find(([path]) => path === "/auth/login")!;
  expect(JSON.parse(loginCall[1].body)).toEqual({ username: "operator", password: "password", surface: "staff", context: "platform" });
  expect(loginCall[2]).toBe("platform"); expect(getAccessToken("platform")).toBe("platform-token");
});

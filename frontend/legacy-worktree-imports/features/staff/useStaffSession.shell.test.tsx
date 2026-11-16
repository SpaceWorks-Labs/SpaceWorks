// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: useStaffSession is not in release 0.12.0 (replaced by useConsoleSession).
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { useStaffSession } from "./useStaffSession";
import { STAFF_ACTIVE_TAB_KEY, STAFF_SELECTED_MAKERSPACE_KEY } from "./staffTabs";

const mocks = vi.hoisted(() => ({ tenant: { mode: "central", makerspaceId: null as number | null }, expired: undefined as (() => void) | undefined,
  request: vi.fn(), refresh: vi.fn(), me: vi.fn(), logout: vi.fn(), wipe: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(),
  staffRequest: mocks.request, refreshAccessToken: mocks.refresh, fetchMe: mocks.me, logout: mocks.logout,
  addAuthExpiredListener: (callback: () => void) => { mocks.expired = callback; return () => {}; },
}));
vi.mock("../../lib/tenant", () => ({ useTenant: () => mocks.tenant }));
vi.mock("../../lib/useLiveUpdates", () => ({ useLiveUpdates: () => {} }));
vi.mock("./eventCheckInOfflineStore", () => ({ wipeOfflineScopes: mocks.wipe }));
const spaces = [{ id: 1, slug: "a", name: "A" }, { id: 2, slug: "b", name: "B" }];
let session: ReturnType<typeof useStaffSession>;
function Probe({ guest }: { guest: boolean }) { session = useStaffSession(guest); const location = useLocation(); return <output>{location.pathname}{location.search}</output>; }
function mount(path: string, guest = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<MemoryRouter initialEntries={[path]}><QueryClientProvider client={client}><Probe guest={guest} /></QueryClientProvider></MemoryRouter>);
  return client;
}
beforeEach(() => {
  localStorage.clear(); vi.clearAllMocks(); mocks.tenant = { mode: "central", makerspaceId: null };
  mocks.refresh.mockResolvedValue(true); mocks.logout.mockResolvedValue(undefined); mocks.wipe.mockResolvedValue(undefined);
  mocks.me.mockResolvedValue({ username: "operator", role: "member", is_superuser: false, makerspaces: spaces.map(space => ({ ...space, actions: ["manage_machines"] })) });
  mocks.request.mockImplementation(async path => path === "/admin/makerspaces" ? spaces : {});
});
it("W21 route membership overrides stored selection during hydrateUser", async () => {
  localStorage.setItem(`${STAFF_SELECTED_MAKERSPACE_KEY}:staff:b`, "1"); mount("/m/b/admin/inventory");
  await waitFor(() => expect(session.restoring).toBe(false)); await waitFor(() => expect(session.activeMakerspace?.id).toBe(2));
  expect(localStorage.getItem(`${STAFF_SELECTED_MAKERSPACE_KEY}:${session.routeMakerspaceSlug ? `staff:${session.routeMakerspaceSlug}` : "platform"}`)).toBe("2");
});
it("W22 delegated member switches organization workspace without changing account", async () => {
  mount("/m/a/admin/machines/12-laser?id=9&surface=delegated"); await waitFor(() => expect(session.restoring).toBe(false)); await waitFor(() => expect(session.activeMakerspace?.id).toBe(1));
  act(() => session.chooseMakerspace(2));
  expect(screen.getByText("/m/b/admin/machines?surface=delegated")).toBeInTheDocument(); expect(localStorage.getItem(`${STAFF_SELECTED_MAKERSPACE_KEY}:member`)).toBe("2");
});
it("W23 guest switching changes selection without navigating", async () => {
  mount("/guest-admin/handover?id=9", true); await waitFor(() => expect(session.restoring).toBe(false)); await waitFor(() => expect(session.activeMakerspace?.id).toBe(1));
  act(() => session.chooseMakerspace(2)); expect(screen.getByText("/guest-admin/handover?id=9")).toBeInTheDocument(); expect(session.selected).toBe(2);
});
it("W24 locked tenant forces its makerspace and switching is a no-op", async () => {
  mocks.tenant = { mode: "single", makerspaceId: 2 }; localStorage.setItem(`${STAFF_SELECTED_MAKERSPACE_KEY}:staff:b`, "1");
  mount("/admin/machines"); await waitFor(() => expect(session.activeMakerspace?.id).toBe(2));
  act(() => session.chooseMakerspace(1)); expect(session.selected).toBe(2);
  act(() => session.chooseMakerspace(null)); expect(session.selected).toBe(2);
});
it("W27 setTab persists and auth expiry clears the remembered destination", async () => {
  mount("/m/a/admin/machines"); await waitFor(() => expect(session.restoring).toBe(false));
  act(() => session.setTab("inventory")); expect(localStorage.getItem(`${STAFF_ACTIVE_TAB_KEY}:staff:a`)).toBe("inventory");
  act(() => mocks.expired?.()); expect(localStorage.getItem(`${STAFF_ACTIVE_TAB_KEY}:staff:a`)).toBeNull();
});
it("W41 signOut logs out, wipes offline scopes, clears selection and query cache", async () => {
  const client = mount("/m/a/admin/machines"); const clear = vi.spyOn(client, "clear");
  await waitFor(() => expect(session.restoring).toBe(false)); await waitFor(() => expect(session.activeMakerspace?.id).toBe(1));
  await act(() => session.signOut()); expect(mocks.logout).toHaveBeenCalledOnce(); expect(mocks.wipe).toHaveBeenCalledWith("session:staff:a:");
  expect(clear).toHaveBeenCalledOnce(); expect(session.user).toBeNull(); expect(session.selected).toBeNull();
});

// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: useStaffSession is not in release 0.12.0 (replaced by useConsoleSession).
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useStaffSession } from "./useStaffSession";

const { refresh, me } = vi.hoisted(() => ({ refresh: vi.fn(), me: vi.fn() }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  refreshAccessToken: refresh, fetchMe: me,
}));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "central", makerspaceId: null }) }));
vi.mock("../../lib/useLiveUpdates", () => ({ useLiveUpdates: vi.fn() }));
vi.mock("./panels/shared", () => ({ useStaffGet: () => ({ data: [], isLoading: false }) }));

describe("staff OIDC callback restoration", () => {
  afterEach(() => { vi.clearAllMocks(); window.history.replaceState(null, "", "/"); });
  it.each(["?code=code&state=state", "?error=access_denied&state=state"])("lets the login panel finish %s before restoring old cookies", async (query) => {
    window.history.replaceState(null, "", `/admin/assigned-events${query}`);
    refresh.mockResolvedValue(true);
    me.mockResolvedValue({ username: "old-member", makerspaces: [] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>;
    const { result } = renderHook(() => useStaffSession(false), { wrapper });
    await waitFor(() => expect(result.current.restoring).toBe(false));
    expect(result.current.user).toBeNull();
    expect(refresh).not.toHaveBeenCalled();
    expect(me).not.toHaveBeenCalled();
  });
});

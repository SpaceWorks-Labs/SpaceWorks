import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { useConsoleSession } from "./useConsoleSession";

const api = vi.hoisted(() => ({
  refreshAccessToken: vi.fn(), fetchMe: vi.fn(), clearAccessToken: vi.fn(), setAccessToken: vi.fn(),
  addAuthExpiredListener: vi.fn(() => () => undefined), logout: vi.fn(), staffRequest: vi.fn(),
}));
vi.mock("../../lib/api", () => api);
const tenant = vi.hoisted(() => ({ value: { mode: "central", makerspaceId: null as number | null } }));
vi.mock("../../lib/tenant", () => ({ useTenant: () => tenant.value }));
vi.mock("../../lib/useLiveUpdates", () => ({ useLiveUpdates: () => undefined }));
vi.mock("./eventCheckInOfflineStore", () => ({ wipeOfflineScopes: () => Promise.resolve() }));
vi.mock("./useSuperadminSpaceHint", () => ({ useSuperadminSpaceHint: () => undefined }));
vi.mock("./panels/shared", () => ({ useStaffGet: () => ({ data: [] }) }));

const person = { id: 1, username: "pat", role: "requester", makerspaces: [], staff_roles: [], is_superuser: false } as never;
const client = new QueryClient();
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/a/admin"]}>{children}</MemoryRouter></QueryClientProvider>);

beforeEach(() => { client.clear(); tenant.value = { mode: "central", makerspaceId: null }; Object.values(api).forEach(mock => mock.mockReset()); api.addAuthExpiredListener.mockReturnValue(() => undefined); });

it("a correct sign-in is not undone by a session restore that was already waiting", async () => {
  let finishRestore: (ok: boolean) => void = () => undefined;
  api.refreshAccessToken.mockResolvedValueOnce(false).mockReturnValueOnce(new Promise<boolean>(resolve => { finishRestore = resolve; }));
  tenant.value = { mode: "central", makerspaceId: null };
  const view = renderHook(() => useConsoleSession(false), { wrapper });
  await waitFor(() => expect(view.result.current.restoring).toBe(false));

  // The space's own domain resolves its tenant, which re-runs the restore; its refresh is now in flight.
  tenant.value = { mode: "single", makerspaceId: 5 };
  view.rerender();
  await waitFor(() => expect(api.refreshAccessToken).toHaveBeenCalledTimes(2));

  // The person signs in (password then authenticator code) while that restore is still waiting.
  act(() => { view.result.current.mfaCompleted({ access: "fresh-token", user: person } as never); });
  expect(view.result.current.user).toBeTruthy();
  api.clearAccessToken.mockClear();

  // The old restore now answers "no session": it must not clear the fresh token or the user.
  await act(async () => { finishRestore(false); await Promise.resolve(); });
  expect(api.clearAccessToken).not.toHaveBeenCalled();
  expect(view.result.current.user).toBeTruthy();
});

it("with no sign-in in between, a failed restore still signs the person out", async () => {
  api.refreshAccessToken.mockResolvedValue(false);
  const { result } = renderHook(() => useConsoleSession(false), { wrapper });
  await waitFor(() => expect(result.current.restoring).toBe(false));
  expect(api.clearAccessToken).toHaveBeenCalled();
  expect(result.current.user).toBeNull();
});

// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: written for string session contexts ("member", "staff:<slug>"); release SessionContext is "person" | "platform".
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken } from "../../lib/api";
import { currentSessionContext, setRouteSessionContext } from "../../lib/api/sessionContext";
import { SessionBoundary } from "../../lib/SessionBoundary";
import { KioskStationPage } from "./KioskStationPage";

vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "central", slug: "" }) }));
vi.mock("./useKioskQueue", () => ({ useKioskQueue: () => ({
  queue: null, setQueue: vi.fn(), online: true, storageError: null, restored: false,
  save: vi.fn(), retry: vi.fn(), reset: vi.fn().mockResolvedValue(undefined),
}) }));
vi.mock("./KioskOnlineScanner", () => ({ KioskOnlineScanner: () => <p>Operator workspace</p> }));

afterEach(() => {
  clearAccessToken("staff:forge"); clearAccessToken("member");
  setRouteSessionContext("member"); vi.unstubAllGlobals();
});

it.each(["/m/forge/kiosk/00000000-0000-0000-0000-000000000001", "/kiosk/00000000-0000-0000-0000-000000000001"])(
  "keeps the PIN bootstrap while selecting staff context at %s", async path => {
    setAccessToken("staff-token", "staff:forge"); setAccessToken("member-token", "member");
    const fetcher = vi.fn(async (url: string, options: RequestInit) => {
      if (url.endsWith("/session/")) {
        expect(new Headers(options.headers).get("Authorization")).toBeNull();
        return new Response(JSON.stringify({ station: { id: 1, name: "Forge desk", kind: "scanner" },
          makerspace: { id: 7, slug: "forge", name: "Forge" }, session_expires_at: "2999-01-01T00:00:00Z",
          permitted_operations: ["resolve_qr"] }), { status: 201 });
      }
      expect(url).toContain("/operator-lease/");
      expect(currentSessionContext()).toBe("staff:forge");
      expect(new Headers(options.headers).get("Authorization")).toBe("Bearer staff-token");
      return new Response(JSON.stringify({ lease_token: "lease", lease_id: "lease-id", expires_at: "2999-01-01T00:00:00Z",
        allowed_actions: ["view_inventory"], permitted_operations: ["resolve_qr"] }), { status: 201 });
    });
    vi.stubGlobal("fetch", fetcher);
    render(<MemoryRouter initialEntries={[path]}><SessionBoundary><Routes>
      <Route path="/m/:slug/kiosk/:stationToken" element={<KioskStationPage />} />
      <Route path="/kiosk/:stationToken" element={<KioskStationPage />} />
    </Routes></SessionBoundary></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Station PIN"), { target: { value: "12345678" } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock station" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Start operator shift" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Start operator shift" }));
    expect(await screen.findByText("Operator workspace")).toBeVisible();
    expect(fetcher).toHaveBeenCalledTimes(2);
  },
);

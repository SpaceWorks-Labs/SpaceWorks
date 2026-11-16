// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: written for string session contexts ("member", "staff:<slug>"); release SessionContext is "person" | "platform".
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken } from "../../lib/api";
import { contextForRoute, setRouteSessionContext } from "../../lib/api/sessionContext";
import { ScannerPage } from "./ScannerPage";

afterEach(() => {
  clearAccessToken("staff:forge"); clearAccessToken("member");
  setRouteSessionContext("member"); vi.unstubAllGlobals();
});

it.each([
  ["/m/forge/scanner", "", ""], ["/scanner", "", "forge"], ["/scanner", "?context=staff%3Aforge", ""],
])("scans from %s with tenant staff credentials", async (path, search, tenant) => {
  setRouteSessionContext(contextForRoute(path, search, tenant));
  setAccessToken("staff-token", "staff:forge"); setAccessToken("member-token", "member");
  const fetcher = vi.fn(async (_url: string, options: RequestInit) => {
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer staff-token");
    return new Response(JSON.stringify({ target: { name: "Scoped drill" }, allowed_actions: [] }), { status: 200 });
  });
  vi.stubGlobal("fetch", fetcher);
  render(<QueryClientProvider client={new QueryClient()}><ScannerPage /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("QR payload"), { target: { value: "qr" } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  expect(await screen.findByRole("heading", { name: "Scoped drill" })).toBeVisible();
  expect(fetcher).toHaveBeenCalledOnce();
});

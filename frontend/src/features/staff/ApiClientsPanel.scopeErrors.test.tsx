import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { ApiClientsPanel } from "./ApiClientsPanel";
import type { Makerspace } from "./StaffPanels";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async importOriginal => ({
  ...await importOriginal<typeof import("../../lib/api")>(), staffRequest,
}));
let client: QueryClient;
afterEach(async () => { cleanup(); await client.cancelQueries(); client.clear(); staffRequest.mockReset(); });

const scopeTarget = "/admin/makerspace/7/api-client-scopes";
const makerspace = { id: 7, name: "Lab", slug: "lab" } as Makerspace;
const apiClient = { id: 9, label: "Test client", client_id: "ck_test", client_type: "server",
  scopes: ["public:read"], allowed_origins: [], is_active: true, last_seen_at: null,
  created_at: "2026-08-20T00:00:00Z" };

it.each([
  { status: 403, code: "permission_denied", detail: "You cannot read this scope catalogue.", retry: false },
  { status: 404, code: "module_disabled", detail: "API access is disabled here.", retry: false },
  { status: 503, code: "service_unavailable", detail: "Scope catalogue is temporarily unavailable.", retry: true },
])("scope drawer handles $status $code with a way to close", async ({ status, code, detail, retry }) => {
  staffRequest.mockImplementation(async (target: string) => {
    if (target.endsWith("/oauth-apps")) return [];
    if (target === scopeTarget) throw new StructuredApiError(status, { code, detail });
    return { results: target === "/admin/makerspace/7/api-clients" ? [apiClient] : [] };
  });
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <ApiClientsPanel makerspace={makerspace} isSuperadmin={false} canManageMakerspace />
  </QueryClientProvider>);
  await waitFor(() => expect(client.getQueryState(["api-client-scopes", 7])?.status).toBe("error"));
  const error = client.getQueryState(["api-client-scopes", 7])!.error as StructuredApiError;
  expect(error).toBeInstanceOf(StructuredApiError);
  expect({ status: error.status, code: error.code }).toEqual({ status, code });
  fireEvent.click(await screen.findByRole("button", { name: "Edit scopes" }));
  const drawer = within(screen.getByRole("dialog"));
  if (retry) {
    const before = staffRequest.mock.calls.filter(([target]) => target === scopeTarget).length;
    fireEvent.click(drawer.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(staffRequest.mock.calls.filter(([target]) => target === scopeTarget)).toHaveLength(before + 1));
    await waitFor(() => expect(client.getQueryState(["api-client-scopes", 7])?.fetchStatus).toBe("idle"));
    const retried = client.getQueryState(["api-client-scopes", 7])!.error as StructuredApiError;
    expect({ status: retried.status, code: retried.code }).toEqual({ status, code });
  } else {
    expect(drawer.getByText(detail, { exact: true })).toBeVisible();
    expect(screen.queryByRole("button", { name: /retry|try again/i })).toBeNull();
    expect(drawer.queryByText(/couldn't load|try again/i)).toBeNull();
  }
  fireEvent.click(drawer.getByRole("button", { name: "Close" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

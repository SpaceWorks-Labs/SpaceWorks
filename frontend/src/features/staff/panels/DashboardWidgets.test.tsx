import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DashboardPanel } from "./DashboardPanel";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
const makerspace = { id: 3, name: "Lab", slug: "lab", public_code: "lab", telegram_group_chat_id: "",
  frontend_domain: null, hidden_from_central_directory: false };
const page = { count: 0, next: null, previous: null, results: [] };
beforeEach(() => { setRouteSessionContext("person");
  request.mockReset();
  request.mockImplementation(async (path: string) => path.endsWith("dashboard") ? { scope_mode: "full" } : page);
});
function show(actions?: string[], allowedTabs?: string[]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><DashboardPanel makerspace={makerspace} canManageMakerspace={false} actions={actions} allowedTabs={allowedTabs} /></MemoryRouter>
  </QueryClientProvider>);
}
it("fails closed without explicit authority and never fetches unpermitted widgets", async () => {
  show(undefined, ["audit", "requests"]);
  await waitFor(() => expect(screen.queryByRole("status", { name: "Loading content" })).toBeNull());
  expect(request).toHaveBeenCalledTimes(1);
  expect(screen.queryByText("Recent activity")).toBeNull();
  expect(screen.queryByText("Due within 3 days")).toBeNull();
});
it.each([["manage_bookings"], ["accept_request", "view_inventory"]])("does not fetch due loans for %s", async (...actions) => {
  show(actions, ["requests", "bookings"]);
  await waitFor(() => expect(screen.queryByRole("status", { name: "Loading content" })).toBeNull());
  expect(request.mock.calls.some(([path]) => path.includes("active-loans"))).toBe(false);
});
it("shows projected audit fields without metadata and links to the scoped audit tab", async () => {
  request.mockImplementation(async (path: string) => path.endsWith("dashboard") ? { scope_mode: "full" }
    : { ...page, results: [{ id: 1, actor_display: "Priya", action_label: "Request issued", created_at: new Date().toISOString(), meta: { secret: "never render" } }] });
  show(["view_audit"], ["audit"]);
  expect(await screen.findByText(/Request issued/)).toBeVisible();
  expect(screen.queryByText(/never render/)).toBeNull();
  expect(screen.getByRole("link", { name: "See all activity →" })).toHaveAttribute("href", "/m/lab/admin/audit");
});
it("loads due loans with the existing active prefix and deep links to the active tab", async () => {
  request.mockImplementation(async (path: string) => path.endsWith("dashboard") ? { scope_mode: "full" }
    : { ...page, results: [{ id: 42, requester_username: "Meera", return_due_at: new Date(Date.now() + 86400000).toISOString(), items: [] }] });
  show(["issue_request"], ["requests"]);
  expect(await screen.findByRole("link", { name: /Meera/ })).toHaveAttribute("href", "/m/lab/admin/requests?queue=active&ordering=return_due_at&id=42");
  expect(request).toHaveBeenCalledWith("/admin/makerspace/3/active-loans?page=1&page_size=24&ordering=return_due_at");
});
it("quick add reuses existing creation targets and supports closing the chooser", async () => {
  show(["edit_inventory", "manage_events"], ["inventory", "events"]);
  fireEvent.click(screen.getByRole("button", { name: "Quick add" }));
  expect(screen.getByRole("dialog", { name: "Quick add" })).toBeVisible();
  expect(screen.getByRole("link", { name: "New item" })).toHaveAttribute("href", "/m/lab/admin/inventory?create=item");
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
});

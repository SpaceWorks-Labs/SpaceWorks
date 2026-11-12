import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ModulesPanel } from "./ModulesPanel";
import { clearToasts, toastStore, undoToast } from "../../components/ui/toastStore";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest: request }));
const module = { key: "events", label: "Events", description: "Bring people together.", installed: false, core: false, available: true, requires: [], pulls_in: [], required_by: [], workflows: ["Event registration"] };
const data = { groups: [{ key: "community", label: "Community", description: "Your people", installed_count: 0, module_count: 2, modules: [module, { ...module, key: "membership", label: "Membership", installed: true, required_by: ["events"] }] }], deployment: { apps: [], env_line: "TOMBSTONED_APPS=", requires_restart: true } };
function show() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); render(<QueryClientProvider client={client}><ModulesPanel makerspaceId={7} /></QueryClientProvider>); return client; }
beforeEach(() => {
  request.mockReset(); clearToasts();
  request.mockImplementation(async (path: string, init?: { method?: string }) => init?.method ? {} : path.endsWith("/modules") ? data : path.endsWith("/roles") ? [] : { id: 7, enabled_features: [] });
});
describe("module settings", () => {
  it("shows accessible switches with the dependency stated before changing anything", async () => {
    show();
    expect(await screen.findByRole("switch", { name: "Events" })).toBeEnabled();
    // Switching a depended-on area off is now allowed: it asks first and switches the dependents off with it.
    expect(screen.getByRole("switch", { name: "Membership" })).toBeEnabled();
    expect(screen.getByText(/Needed by Events\./)).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
  it("retains the install API, refreshes the gates and awaits the inverse API for Undo", async () => {
    const client = show(); const invalidation = vi.spyOn(client, "invalidateQueries");
    fireEvent.click(await screen.findByRole("switch", { name: "Events" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/modules/install", { method: "POST", body: JSON.stringify({ key: "events" }) }));
    await waitFor(() => expect(toastStore.snapshot().some(row => row.message === "Events switched on.")).toBe(true));
    expect(invalidation).toHaveBeenCalledWith({ queryKey: ["staff", "makerspaces"] });
    const notification = toastStore.snapshot().find(row => row.undo)!;
    await undoToast(notification.id);
    expect(request).toHaveBeenCalledWith("/admin/makerspace/7/modules/uninstall", { method: "POST", body: JSON.stringify({ key: "events" }) });
  });
  it("offers retry after a failed load", async () => {
    request.mockRejectedValueOnce(new Error("Network")); show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load modules. Try again.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("switch", { name: "Events" })).toBeVisible();
  });
});

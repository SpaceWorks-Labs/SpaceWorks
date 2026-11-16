import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ModulesPanel } from "./ModulesPanel";
import { clearToasts, toastStore, undoToast } from "../../components/ui/toastStore";
import { modulesData, rolesData, settingsData } from "./modules/test/moduleFixtures";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest: request }));

function show() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); render(<QueryClientProvider client={client}><ModulesPanel makerspaceId={7} /></QueryClientProvider>); }
const calls = () => request.mock.calls.filter(([, init]) => init?.method === "POST" || init?.method === "PATCH").map(([path, init]) => `${init.method} ${path} ${init.body}`);
beforeEach(() => {
  request.mockReset(); clearToasts();
  request.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (init?.method) return {};
    if (path.endsWith("/modules")) return modulesData;
    if (path.endsWith("/roles")) return rolesData;
    return settingsData;
  });
});

describe("modules by area", () => {
  it("groups cards under their area with counts", async () => {
    show();
    expect(await screen.findByRole("heading", { level: 2, name: "Events" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 3, name: "Bookings" })).toBeVisible();
    expect(screen.getByText("2 of 2 switched on")).toBeVisible();
  });
  it("shows a platform-locked switch as disabled with its reason", async () => {
    show();
    const sms = await screen.findByRole("switch", { name: "SMS" });
    expect(sms).toBeDisabled();
    expect(screen.getByText(/usage limit on this hosting plan/)).toBeVisible();
    expect(screen.getByText(/Not installed on this server/)).toBeVisible();
    expect(screen.getAllByText(/Always on\. This is part of the core system/).length).toBeGreaterThan(0);
    fireEvent.click(sms);
    expect(calls()).toEqual([]);
  });
  it("searches names, descriptions and keys, and filters by state", async () => {
    show();
    await screen.findByRole("switch", { name: "SMS" });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "event_reimb" } });
    expect(screen.getByRole("heading", { level: 3, name: "Event reimbursements" })).toBeVisible();
    expect(screen.queryByRole("heading", { level: 3, name: "Bookings" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /^Locked/ }));
    expect(screen.queryByRole("heading", { level: 3, name: "Bookings" })).toBeNull();
    expect(screen.getByRole("heading", { level: 3, name: "SMS" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /^Off/ }));
    expect(screen.getByRole("heading", { level: 3, name: "Bookings" })).toBeVisible();
  });
  it("opens a card whose feature matches the search", async () => {
    show();
    await screen.findByRole("switch", { name: "Bookings" });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "recurring bookings" } });
    expect(await screen.findByRole("switch", { name: "Recurring bookings" })).toBeVisible();
  });
  it("switches on without a prompt when nothing depends on it, and Undo reverses it", async () => {
    show();
    fireEvent.click(await screen.findByRole("switch", { name: "Bookings" }));
    await waitFor(() => expect(calls()).toEqual(['POST /admin/makerspace/7/modules/install {"key":"bookings"}']));
    await waitFor(() => expect(toastStore.snapshot().some(row => row.message === "Bookings switched on.")).toBe(true));
    await undoToast(toastStore.snapshot().find(row => row.undo)!.id);
    expect(calls()).toContain('POST /admin/makerspace/7/modules/uninstall {"key":"bookings"}');
  });
});

describe("dependency prompts", () => {
  it("confirms before switching off a parent, listing dependents, then switches dependents off first", async () => {
    show();
    fireEvent.click(await screen.findByRole("switch", { name: "Events" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Event reimbursements \(needs Events\)/)).toBeVisible();
    expect(calls()).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Switch off" }));
    await waitFor(() => expect(calls().filter(call => call.includes("/modules/"))).toEqual([
      'POST /admin/makerspace/7/modules/uninstall {"key":"event_reimbursements"}',
      'POST /admin/makerspace/7/modules/uninstall {"key":"events"}']));
  });
  it("cancelling the confirm changes nothing", async () => {
    show();
    fireEvent.click(await screen.findByRole("switch", { name: "Events" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(calls()).toEqual([]);
  });
  it("offers to switch the parent on when a feature of an off area is switched on", async () => {
    show();
    const toggle = (await screen.findAllByRole("button", { name: /^Features:/ })).find(button => button.closest("article")?.querySelector("h3")?.textContent === "Bookings")!;
    fireEvent.click(toggle);
    fireEvent.click(await screen.findByRole("switch", { name: "Recurring bookings" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/only works while Bookings is on/)).toBeVisible();
    fireEvent.click(within(dialog).getByRole("button", { name: "Switch on both" }));
    await waitFor(() => expect(calls().some(call => call.includes("PATCH") && call.includes("bookings.recurring"))).toBe(true));
    expect(calls()[0]).toContain("/modules/install");
  });
  it("bulk switches an area off after a confirm that lists what changes", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Switch off all of Events" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Event reimbursements")).toBeVisible();
    fireEvent.click(within(dialog).getByRole("button", { name: "Switch all off" }));
    await waitFor(() => expect(calls().filter(call => call.includes("uninstall")).length).toBe(2));
  });
});

describe("modules by role", () => {
  it("shows only what a role uses, worked out from its actions", async () => {
    show();
    fireEvent.click(await screen.findByRole("radio", { name: "By role" }));
    fireEvent.click(await screen.findByRole("radio", { name: "Front desk" }));
    expect(screen.getByRole("heading", { level: 3, name: "Bookings" })).toBeVisible();
    expect(screen.queryByRole("heading", { level: 3, name: "Events" })).toBeNull();
    expect(screen.getByText(/uses 1 of 7 areas/)).toBeVisible();
    fireEvent.click(screen.getByRole("radio", { name: "Space Manager" }));
    expect(screen.getByRole("heading", { level: 3, name: "Events" })).toBeVisible();
  });
});

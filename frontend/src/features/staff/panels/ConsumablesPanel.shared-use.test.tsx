import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { StaffListContext } from "../StaffListContext";
import { ConsumablesPanel } from "./ConsumablesPanel";
import type { Makerspace } from "./shared";

const mock = vi.hoisted(() => ({ request: vi.fn(), owner: "1", listener: undefined as undefined | ((c: string) => void) }));
vi.mock("../../../lib/api", () => ({ staffRequest: mock.request }));
vi.mock("../../../lib/api/sessionContext", () => ({ onSessionCleared: (fn: (c: string) => void) => { mock.listener = fn; return () => {}; } }));
vi.mock("../../../lib/api/sessionTokens", () => ({ getSessionOwner: () => mock.owner }));
vi.mock("../../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: mock.owner }) }));
vi.mock("../../../lib/features", () => ({ capabilityOn: () => true }));
const row = { source: "item", id: 1, name: "Solder", machine_id: null, machine_name: "", unit: "count", remaining: "9", threshold: null, status: "ok", open_to_buy_id: null };
function setup(actorId = 1, actions: string[] = [], tenant = 777) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId, actions }}><ConsumablesPanel makerspace={{ id: tenant, slug: "space", name: "Space" } as Makerspace} canEditInventory /></StaffListContext.Provider></MemoryRouter></QueryClientProvider>);
}
function prepare(post: (body: string) => Promise<unknown>) {
  mock.owner = "1"; mock.request.mockReset(); mock.request.mockImplementation((path: string, init?: RequestInit) => {
    if (init?.method === "POST") return post(String(init.body));
    if (path.includes("equipment-sources")) return Promise.resolve({ count: 1, next: null, previous: null, results: [{ kind: "plan", id: 3, planned_quantity: 2, used_quantity: 0 }] });
    return Promise.resolve({ count: 1, next: null, previous: null, results: [row] });
  });
}
async function open() { fireEvent.click(await screen.findByRole("button", { name: "Log use" })); await screen.findByRole("button", { name: /Consumable plan/ }); return screen.getByRole("dialog"); }
function deferred() { let resolve!: (value: unknown) => void; const promise = new Promise<unknown>(r => { resolve = r; }); return { promise, resolve }; }

it.each(["ordinary", "linked"])("prevents the other use while a %s request is pending", async direction => {
  const held = deferred(); const calls: string[] = []; prepare(body => { calls.push(body); return held.promise; }); setup(); const dialog = await open();
  fireEvent.click(within(dialog).getByRole("button", { name: /Consumable plan/ }));
  if (direction === "ordinary") { const captured = within(dialog).getByRole("button", { name: "Record linked use" }); fireEvent.click(within(dialog).getByRole("button", { name: "Log use" })); fireEvent.click(captured); }
  else { fireEvent.click(within(dialog).getByRole("button", { name: "Record linked use" })); fireEvent.submit(within(dialog).getByRole("button", { name: "Log use" }).closest("form")!); }
  await waitFor(() => expect(calls).toHaveLength(1)); held.resolve(direction === "ordinary" ? row : { status: "recorded", replayed: false });
});

it("keeps an uncertain ordinary use fenced across panel remount and directs the user to a manager", async () => {
  const bodies: string[] = []; prepare(body => { bodies.push(body); return Promise.reject(new Error("offline")); });
  const page = setup(); let dialog = await open();
  fireEvent.click(within(dialog).getByRole("button", { name: "Log use" }));
  await screen.findByText(/result may be unknown/i); page.unmount();
  setup(); fireEvent.click(await screen.findByRole("button", { name: "Log use" })); dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("button", { name: "Log use" })).toBeDisabled();
  expect(within(dialog).queryByRole("button", { name: "Record linked use" })).not.toBeInTheDocument();
  fireEvent.submit(within(dialog).getByRole("button", { name: "Log use" }).closest("form")!);
  expect(bodies).toHaveLength(1);
  expect(within(dialog).getByText(/Ask a manager to review/)).toBeInTheDocument();
  expect(within(dialog).getByRole("button", { name: "Log use" })).toBeDisabled();
});

it("offers explicit audit review recovery only to an actor with audit access", async () => {
  prepare(() => Promise.reject(new Error("offline"))); setup(1, ["view_audit"], 778);
  const dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: "Log use" }));
  const acknowledgement = await screen.findByRole("button", { name: "I reviewed the audit log" });
  expect(within(dialog).getByRole("link", { name: "Open audit log" })).toHaveAttribute("href", "/m/space/admin/audit");
  fireEvent.click(acknowledgement);
  expect(within(dialog).getByRole("button", { name: "Log use" })).toBeEnabled();
});

it("releases the ordinary fence after a first definitive 400", async () => {
  let calls = 0; prepare(() => { calls++; return Promise.reject(Object.assign(new Error("invalid"), { status: 400 })); });
  setup(1, [], 781); const dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: "Log use" }));
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "Log use" })).toBeEnabled());
  expect(within(dialog).queryByText(/result may be unknown/i)).not.toBeInTheDocument(); expect(calls).toBe(1);
});

it("keeps both paths fenced after a post-effect 500 through panel remount", async () => {
  let effects = 0; prepare(() => { effects++; return Promise.reject(Object.assign(new Error("response serialization failed"), { status: 500 })); });
  const page = setup(1, [], 782); let dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: "Log use" }));
  await screen.findByText(/result may be unknown/i); page.unmount(); setup(1, [], 782);
  fireEvent.click(await screen.findByRole("button", { name: "Log use" })); dialog = screen.getByRole("dialog");
  expect(within(dialog).getByRole("button", { name: "Log use" })).toBeDisabled();
  expect(within(dialog).queryByRole("button", { name: "Record linked use" })).not.toBeInTheDocument();
  fireEvent.submit(within(dialog).getByRole("button", { name: "Log use" }).closest("form")!); expect(effects).toBe(1);
});

it("does not let a late old-owner completion clear the new owner's unknown fence", async () => {
  const old = deferred(); let calls = 0; prepare(() => { calls++; return calls === 1 ? old.promise : Promise.reject(new Error("offline after send")); });
  const page = setup(1, [], 783); let dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: "Log use" }));
  await waitFor(() => expect(calls).toBe(1)); mock.owner = "2"; act(() => { mock.listener?.("person"); }); page.unmount();
  setup(2, [], 783); dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: "Log use" }));
  await screen.findByText(/result may be unknown/i); await act(async () => { old.resolve(row); await old.promise; });
  expect(within(dialog).getByRole("button", { name: "Log use" })).toBeDisabled();
  fireEvent.submit(within(dialog).getByRole("button", { name: "Log use" }).closest("form")!); expect(calls).toBe(2);
});

it("retries the original uncertain use after the panel remounts", async () => {
  const bodies: string[] = []; prepare(body => { bodies.push(body); return bodies.length === 1 ? Promise.reject(new Error("offline")) : Promise.resolve({ status: "recorded", replayed: true }); });
  const page = setup(); let dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: /Consumable plan/ })); fireEvent.click(within(dialog).getByRole("button", { name: "Record linked use" }));
  await screen.findByRole("button", { name: "Retry the same use" }); page.unmount(); setup(); dialog = await open(); fireEvent.click(within(dialog).getByRole("button", { name: "Retry the same use" }));
  await waitFor(() => expect(bodies).toHaveLength(2)); expect(bodies[1]).toBe(bodies[0]);
});


it("conceals captured controls during the pre-token owner mismatch and resumes for the verified new actor", async () => {
  prepare(() => Promise.resolve({ status: "recorded", replayed: false }));
  const page = setup(); const dialog = await open();
  fireEvent.click(within(dialog).getByRole("button", { name: /Consumable plan/ }));
  const linkedButton = within(dialog).getByRole("button", { name: "Record linked use" });
  const ordinaryForm = within(dialog).getByRole("button", { name: "Log use" }).closest("form")!;
  mock.request.mockClear();
  mock.owner = "2"; act(() => { mock.listener?.("person"); });
  fireEvent.click(linkedButton); fireEvent.submit(ordinaryForm);
  expect(mock.request.mock.calls.some(call => String(call[0]).includes("equipment-sources") || call[1]?.method === "POST")).toBe(false);
  page.unmount(); setup(2);
  fireEvent.click(await screen.findByRole("button", { name: "Log use" }));
  expect(await screen.findByRole("button", { name: /Consumable plan/ })).toBeInTheDocument();
  expect(mock.request.mock.calls.some(call => String(call[0]).includes("equipment-sources"))).toBe(true);
});


it("does not open product-source use for machine or pool rows sharing an item ID", async () => {
  prepare(() => Promise.resolve(row));
  mock.request.mockImplementation((path: string, init?: RequestInit) => {
    if (init?.method === "POST" || path.includes("equipment-sources")) throw new Error("Unexpected product request");
    return Promise.resolve({ count: 3, next: null, previous: null, results: [row, { ...row, source: "machine", name: "Machine supply" }, { ...row, source: "pool", name: "Pool supply" }] });
  });
  setup(); await screen.findByText("Machine supply");
  expect(screen.getAllByRole("button", { name: "Log use" })).toHaveLength(1);
  expect(mock.request.mock.calls.some(call => String(call[0]).includes("equipment-sources") || call[1]?.method === "POST")).toBe(false);
});

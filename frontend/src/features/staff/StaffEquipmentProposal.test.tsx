import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { StaffEquipmentProposal } from "./StaffEquipmentProposal";
import { PendingIntake, type StaffBody } from "../inventory/contextualIntake";
import { StaffListContext } from "./StaffListContext";
const mock = vi.hoisted(() => ({ request: vi.fn(), owner: "1" }));
vi.mock("../../lib/api", () => ({ staffRequest: mock.request, memberRequest: vi.fn() }));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: mock.owner }) }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionOwner: () => mock.owner }));

it.each(["event", "booking"] as const)("retains a both-context %s intent while its counterpart is off", async domain => {
  mock.owner = "1"; mock.request.mockReset();
  mock.request.mockResolvedValue({ results: [], next: null, previous: null });
  const owner = new PendingIntake<StaffBody>();
  const scope = JSON.stringify(["person", "1", 1, 4, domain, 9, 3]);
  const body: StaffBody = { operation_id: "fixed", event_registration_id: 3, booking_id: 6, requested_for: "Workshop", items: [{ product_id: 8, quantity: 1 }] };
  owner.begin(scope, body);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = (counterpart: boolean) => <QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["staff_admin", ...(domain === "event" || counterpart ? ["events"] : []), ...(domain === "booking" || counterpart ? ["bookings"] : [])], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain={domain} resourceId={9} targetId={3} pendingOwner={owner}  /></StaffListContext.Provider></QueryClientProvider>;
  const view = render(tree(false)); fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  expect(screen.getByRole("button", { name: "Retry the same request" })).toBeDisabled();
  expect(screen.queryByRole("checkbox", { name: /Also link/ })).toBeNull();
  expect(owner.current(scope)).toEqual(body);
  view.rerender(tree(true));
  expect(screen.getByRole("button", { name: "Retry the same request" })).toBeEnabled();
  expect(owner.current(scope)).toEqual(body);
  expect(mock.request.mock.calls.filter(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toHaveLength(0);
});

it("offers a consumable-only kit without fetching loan products", async () => {
  mock.owner = "1"; mock.request.mockReset();
  mock.request.mockImplementation((path: string) => path.includes("equipment-kits")
    ? Promise.resolve({ results: [{ id: 9, name: "Materials", version: 2, lines: [{ product_id: 3, display_name: "Glue", quantity_per_person: 1, kind: "consumable" }] }], next: null, previous: null })
    : Promise.resolve({ kind: "consumable_plan", plan_id: 1, replayed: false }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "staff_admin"], enabled_features: ["inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByRole("button", { name: "Materials" }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  await waitFor(() => expect(mock.request.mock.calls.some(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toBe(true));
  expect(mock.request.mock.calls.some(call => String(call[0]).includes("equipment-request-products"))).toBe(false);
});

it("hides the proposal when lending and consumables are both off", () => {
  mock.owner = "1"; const client = new QueryClient();
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "staff_admin"], enabled_features: [] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  expect(screen.queryByRole("button", { name: "Propose equipment" })).toBeNull();
});

it("does not retry a retained kit whose kind is unknown after a capability turns off", () => {
  mock.owner = "1"; const client = new QueryClient(); const owner = new PendingIntake<StaffBody>();
  const scope = JSON.stringify(["person", "1", 1, 4, "event", 9, 3]);
  const body: StaffBody = { operation_id: "held", event_registration_id: 3, booking_id: null, requested_for: "Workshop", kit: { id: 9, version: 2 } };
  owner.begin(scope, body);
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "staff_admin"], enabled_features: ["inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={owner} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  expect(screen.getByRole("button", { name: "Retry the same request" })).toBeDisabled();
  expect(owner.current(scope)).toEqual(body);
});

it("retries an exact locally verified consumable kit while lending is off", async () => {
  mock.owner = "1"; mock.request.mockReset();
  mock.request.mockImplementation((path: string) => path.includes("equipment-kits")
    ? Promise.resolve({ results: [{ id: 9, name: "Materials", version: 2, lines: [{ product_id: 3, display_name: "Glue", quantity_per_person: 1, kind: "consumable" }] }], next: null, previous: null })
    : Promise.reject(new Error("network unavailable")));
  const owner = new PendingIntake<StaffBody>(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "staff_admin"], enabled_features: ["inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={owner} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByRole("button", { name: "Materials" }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  const retry = await screen.findByRole("button", { name: "Retry the same request" });
  expect(retry).toBeEnabled(); fireEvent.click(retry);
  await waitFor(() => expect(mock.request.mock.calls.filter(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toHaveLength(2));
  const bodies = mock.request.mock.calls.filter(call => String(call[0]).endsWith("/equipment-requests/contextual")).map(call => call[1].body);
  expect(bodies[1]).toBe(bodies[0]);
});

it("hides an unscoped or foreign makerspace proposal", () => {
  mock.owner = "1"; const client = new QueryClient();
  const view = render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1 }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  expect(screen.queryByRole("button", { name: "Propose equipment" })).toBeNull();
  view.rerender(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 5, enabled_modules: ["events", "staff_admin"], enabled_features: ["loans.enabled"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  expect(screen.queryByRole("button", { name: "Propose equipment" })).toBeNull();
});

it("reconciles a replacement form when the previous submission completes", async () => {
  mock.owner = "1"; let resolve!: (value: unknown) => void; const delayed = new Promise<unknown>(done => { resolve = done; });
  mock.request.mockReset(); mock.request.mockImplementation((path: string) => path.includes("equipment-request-products")
    ? Promise.resolve({ results: [{ id: 8, name: "Drill" }], next: null, previous: null })
    : path.includes("equipment-kits") ? Promise.resolve({ results: [], next: null, previous: null }) : delayed);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); const owner = new PendingIntake<StaffBody>();
  const component = () => <QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "bookings", "staff_admin"], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={owner} /></StaffListContext.Provider></QueryClientProvider>;
  const first = render(component()); fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByLabelText("Drill")); fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" })); first.unmount();
  render(component()); fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  expect(await screen.findByRole("button", { name: "Retry the same request" })).toBeInTheDocument();
  resolve({ kind: "request", request_id: 10, status: "pending_approval", replayed: false });
  await waitFor(() => expect(screen.queryByRole("button", { name: "Retry the same request" })).not.toBeInTheDocument());
});

it("lets a domain manager propose for the source without a supplied borrower", async () => {
  const originalPath = window.location.pathname;
  mock.request.mockReset();
  mock.request.mockImplementation((path: string) => path.includes("equipment-request-products")
    ? Promise.resolve({ results: [{ id: 8, name: "Drill" }], next: null, previous: null })
    : path.includes("equipment-kits") ? Promise.resolve({ results: [], next: null, previous: null })
    : Promise.resolve({ kind: "request", request_id: 10, status: "pending_approval", replayed: false }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "bookings", "staff_admin"], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: /Drill/ }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  await waitFor(() => expect(mock.request.mock.calls.some(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toBe(true));
  expect(mock.request.mock.calls.some(call => call[0] === "/admin/makerspace/4/events/9/equipment-request-products?page=1")).toBe(true);
  const body = JSON.parse(mock.request.mock.calls.find(call => String(call[0]).endsWith("/equipment-requests/contextual"))![1].body);
  expect(body.event_registration_id).toBe(3); expect(body.booking_id).toBeNull(); expect(body.borrower_id).toBeUndefined();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Issue" })).toBeNull();
  expect(window.location.pathname).toBe(originalPath);
});

it("keeps the same uncertain operation after a later denial", async () => {
  let attempts = 0; mock.request.mockReset();
  mock.request.mockImplementation((path: string) => {
    if (path.includes("equipment-request-products")) return Promise.resolve({ results: [{ id: 8, name: "Drill" }], next: null, previous: null });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    attempts++; return Promise.reject(attempts === 1 ? new Error("offline") : Object.assign(new Error("denied"), { status: 403 }));
  });
  const owner = new PendingIntake<StaffBody>();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "bookings", "staff_admin"], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={owner} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: /Drill/ }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry the same request" }));
  await waitFor(() => expect(attempts).toBe(2));
  const calls = mock.request.mock.calls.filter(call => String(call[0]).endsWith("/equipment-requests/contextual"));
  expect(calls[0][1].body).toBe(calls[1][1].body);
  expect(screen.queryByRole("checkbox", { name: /Drill/ })).toBeNull();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
});

it("submits an independently selected booking with the source event registration", async () => {
  mock.request.mockReset(); mock.request.mockImplementation((path: string) => {
    if (path.includes("equipment-request-products")) return Promise.resolve({ results: [{ id: 8, name: "Drill" }], next: null, previous: null });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    if (path.includes("/makerspaces/4/spaces/")) return Promise.resolve({ results: [{ id: 5, name: "Room" }], next: null, previous: null });
    if (path.includes("/spaces/5/bookings/")) return Promise.resolve({ results: [{ id: 6 }], next: null, previous: null });
    return Promise.resolve({ kind: "request", request_id: 10, status: "pending_approval", replayed: false });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "bookings", "staff_admin"], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(screen.getByLabelText("Also link a booking"));
  fireEvent.click(await screen.findByRole("button", { name: "Room" }));
  fireEvent.click(await screen.findByRole("button", { name: "Booking #6" }));
  fireEvent.click(await screen.findByLabelText("Drill"));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  await waitFor(() => expect(mock.request.mock.calls.some(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toBe(true));
  const body = JSON.parse(mock.request.mock.calls.find(call => String(call[0]).endsWith("/equipment-requests/contextual"))![1].body);
  expect(body).toMatchObject({ event_registration_id: 3, booking_id: 6 });
  expect(body.borrower_id).toBeUndefined();
});

it("hides the form and starts no new source requests when owner changes before the verified actor", async () => {
  mock.owner = "1"; mock.request.mockReset();
  mock.request.mockResolvedValue({ results: [], next: null, previous: null });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const renderTree = () => <QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "bookings", "staff_admin"], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>;
  const view = render(renderTree());
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  await waitFor(() => expect(mock.request).toHaveBeenCalled());
  const before = mock.request.mock.calls.length;
  mock.owner = "2"; view.rerender(renderTree());
  expect(screen.queryByRole("button", { name: "Submit for review" })).toBeNull();
  expect(mock.request.mock.calls.length).toBe(before);
  mock.owner = "1";
});

it("requires a registration when linking an event to a source booking", async () => {
  mock.owner = "1"; mock.request.mockReset(); mock.request.mockImplementation((path: string) => {
    if (path.includes("equipment-request-products")) return Promise.resolve({ results: [{ id: 8, name: "Drill" }], next: null, previous: null });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    if (path.includes("accessible-events")) return Promise.resolve({ results: [{ id: 9, title: "Workshop" }], next: null, previous: null });
    if (path.includes("/events/9/registrations/")) return Promise.resolve({ results: [{ id: 3, name: "Attendee" }], next: null, previous: null });
    return Promise.resolve({ kind: "request", request_id: 10, status: "pending_approval", replayed: false });
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "bookings", "staff_admin"], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="booking" resourceId={5} targetId={6} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(screen.getByLabelText("Also link an event"));
  fireEvent.click(await screen.findByRole("button", { name: "Workshop" }));
  fireEvent.click(await screen.findByRole("button", { name: "Attendee" }));
  fireEvent.click(await screen.findByLabelText("Drill"));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Build" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  await waitFor(() => expect(mock.request.mock.calls.some(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toBe(true));
  const body = JSON.parse(mock.request.mock.calls.find(call => String(call[0]).endsWith("/equipment-requests/contextual"))![1].body);
  expect(body).toMatchObject({ event_registration_id: 3, booking_id: 6 });
  expect(body.borrower_id).toBeUndefined();
});

it("rejects a stale submit handler before React renders the new owner", async () => {
  mock.owner = "1"; mock.request.mockReset();
  mock.request.mockImplementation((path: string) => Promise.resolve(path.includes("equipment-request-products")
    ? { results: [{ id: 8, name: "Drill" }], next: null, previous: null }
    : { results: [], next: null, previous: null }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "bookings", "staff_admin"], enabled_features: ["loans.enabled", "inventory.consumables"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByLabelText("Drill"));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  const oldButton = screen.getByRole("button", { name: "Submit for review" });
  mock.owner = "2";
  fireEvent.click(oldButton);
  expect(mock.request.mock.calls.some(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toBe(false);
  mock.owner = "1";
});

it("shows stored availability and submits the chosen quantity", async () => {
  mock.owner = "1"; mock.request.mockReset();
  mock.request.mockImplementation((path: string) => path.includes("equipment-request-products")
    ? Promise.resolve({ results: [{ id: 8, name: "Drill", available_quantity: 3, next_due_back_at: null }, { id: 9, name: "Saw" }], next: null, previous: null })
    : path.includes("equipment-kits") ? Promise.resolve({ results: [], next: null, previous: null })
    : Promise.resolve({ kind: "request", request_id: 5, status: "pending_approval", replayed: false }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: 1, makerspace: { id: 4, enabled_modules: ["events", "staff_admin"], enabled_features: ["loans.enabled"] } }}><StaffEquipmentProposal tenant={4} domain="event" resourceId={9} targetId={3} pendingOwner={new PendingIntake<StaffBody>()} /></StaffListContext.Provider></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Propose equipment" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Drill" }));
  expect(screen.getByText("3 available now")).toBeTruthy();
  expect(screen.getAllByText(/available now/)).toHaveLength(1);
  fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
  await waitFor(() => expect(mock.request.mock.calls.some(call => String(call[0]).endsWith("/equipment-requests/contextual"))).toBe(true));
  const call = mock.request.mock.calls.find(item => String(item[0]).endsWith("/equipment-requests/contextual"));
  expect(JSON.parse(String(call?.[1]?.body)).items).toEqual([{ product_id: 8, quantity: 2 }]);
});

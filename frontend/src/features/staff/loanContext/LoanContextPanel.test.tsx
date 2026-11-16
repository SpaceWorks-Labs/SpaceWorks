import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { StaffListContext } from "../StaffListContext";
import { LoanContextPanel } from "./LoanContextPanel";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: mocks.request }));
vi.mock("./scope", () => ({ useSessionScope: () => ({ context: "person", generation: 1 }) }));
const generation = "11111111-1111-4111-8111-111111111111";
const booking = (id: number, revision = 1) => ({ active: true, generation, revision, booking_id: id, can_write: true });
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; };
function view(client: QueryClient, actor: number, tenant = 1, modules = ["bookings"], actions = ["accept_request"]) {
  return <MemoryRouter><QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "staff", canShare: false, actorId: actor, actions }}>
    <LoanContextPanel tenant={tenant} request={44} modules={modules} />
  </StaffListContext.Provider></QueryClientProvider></MemoryRouter>;
}
beforeEach(() => { mocks.request.mockReset(); });

it("hides late actor A response immediately after actor B or tenant changes", async () => {
  const a = deferred<unknown>(); mocks.request.mockReturnValueOnce(a.promise).mockResolvedValue(booking(22));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendered = render(view(client, 1));
  await waitFor(() => expect(mocks.request).toHaveBeenCalledTimes(1));
  rendered.rerender(view(client, 2, 1));
  await screen.findByText("Booking #22");
  rendered.rerender(view(client, 2, 2));
  await screen.findByText("Booking #22");
  await act(async () => a.resolve(booking(91)));
  expect(screen.queryByText("Booking #91")).toBeNull();
  expect(screen.getByText("Booking #22")).toBeTruthy();
});

it("hides a populated context when permission fails or module turns off", async () => {
  mocks.request.mockResolvedValueOnce(booking(71)).mockRejectedValue(new Error("403"));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendered = render(view(client, 1));
  await screen.findByText("Booking #71");
  await act(async () => { await client.invalidateQueries({ queryKey: ["loan-context"] }); });
  await screen.findByText("Context is unavailable for this access.");
  expect(screen.queryByText("Booking #71")).toBeNull();
  rendered.rerender(view(client, 1, 1, []));
  expect(screen.queryByText("Booking #71")).toBeNull();
  expect(screen.queryByLabelText("Booking context")).toBeNull();
});

it("does not replay a conflicting write and keeps the draft for explicit review", async () => {
  mocks.request.mockResolvedValueOnce(booking(7, 1)).mockRejectedValueOnce(new Error("409 context_generation_changed"))
    .mockResolvedValueOnce({ ...booking(7, 1), generation: "22222222-2222-4222-8222-222222222222" });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(view(client, 1));
  await screen.findByText("Booking #7");
  fireEvent.click(screen.getByRole("button", { name: "Edit or remove" }));
  expect(screen.getByText("Proposed booking #7")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Save context" }));
  await screen.findByRole("button", { name: "Review latest state" });
  await waitFor(() => expect(mocks.request).toHaveBeenCalledTimes(3));
  expect(screen.getByText("Proposed booking #7")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Save context" })).toBeDisabled();
  expect(mocks.request.mock.calls.filter(call => call[1]?.method === "PUT")).toHaveLength(1);
});


it.each([
  { status: 403, code: "permission_denied" },
  { status: 404, code: "module_disabled" },
])("clears populated editor immediately on mutation denial %#", async failure => {
  const deferredReread = deferred<unknown>();
  mocks.request.mockResolvedValueOnce(booking(71)).mockRejectedValueOnce(Object.assign(new Error("denied"), failure))
    .mockReturnValueOnce(deferredReread.promise);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(view(client, 1));
  await screen.findByText("Booking #71");
  fireEvent.click(screen.getByRole("button", { name: "Edit or remove" }));
  expect(screen.getByText("Proposed booking #71")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Save context" }));
  await screen.findByText("Context is unavailable for this access.");
  expect(screen.queryByText("Booking #71")).toBeNull();
  expect(screen.queryByText("Proposed booking #71")).toBeNull();
  expect(screen.queryByRole("button", { name: "Save context" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Choose a different resource" })).toBeNull();
  expect(mocks.request).toHaveBeenCalledTimes(2); // no pending reread needed to conceal
  expect(client.getQueriesData({ queryKey: ["loan-context"] }).every(([, data]) => data === undefined)).toBe(true);
});

it("shows actionable validation without pretending the context changed", async () => {
  mocks.request.mockResolvedValueOnce(booking(7)).mockRejectedValueOnce(
    Object.assign(new Error("The selected participant does not belong to this event."), { status: 400 }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(view(client, 1));
  await screen.findByText("Booking #7");
  fireEvent.click(screen.getByRole("button", { name: "Edit or remove" }));
  fireEvent.click(screen.getByRole("button", { name: "Save context" }));
  await screen.findByText("The selected participant does not belong to this event.");
  expect(screen.queryByRole("button", { name: "Review latest state" })).toBeNull();
  expect(mocks.request).toHaveBeenCalledTimes(2);
});


it("shows a hidden-participant event read-only without exposing its presence", async () => {
  mocks.request.mockResolvedValueOnce({ active: true, generation, revision: 1, event_id: 31,
    may_view_participant: false, can_write: false });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(view(client, 1, 1, ["events"], ["accept_request", "manage_events"]));
  await screen.findByText("Event #31");
  expect(screen.getByText("Participant details are unavailable for this access.")).toBeTruthy();
  expect(screen.getByText("Changes require the appropriate request and event registration permissions and an editable request.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Edit or remove" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Choose a different resource" })).toBeNull();
  expect(mocks.request).toHaveBeenCalledTimes(1);
});

it("allows server-authorized event editing with participant visibility", async () => {
  mocks.request.mockResolvedValueOnce({ active: true, generation, revision: 1, event_id: 31,
    may_view_participant: true, participant_registration_id: null, can_write: true })
    .mockResolvedValueOnce({ results: [], next: null, previous: null });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(view(client, 1, 1, ["events"], ["accept_request", "manage_events"]));
  await screen.findByText("Event #31");
  fireEvent.click(screen.getByRole("button", { name: "Edit or remove" }));
  expect(screen.getByRole("button", { name: "Save context" })).toBeEnabled();
  await screen.findByRole("button", { name: "No participant" });
});


it("starts participant pagination at page one when the selected event changes", async () => {
  const event = { active: true, generation, revision: 1, event_id: 31,
    may_view_participant: true, participant_registration_id: null, can_write: true };
  mocks.request.mockImplementation((path: string) => {
    if (path.includes("/event-context")) return Promise.resolve(event);
    if (path === "/admin/events/31/registrations/?page=1") return Promise.resolve({ results: [{ id: 1, name: "First" }], next: "next", previous: null });
    if (path === "/admin/events/31/registrations/?page=2") return Promise.resolve({ results: [{ id: 2, name: "Second" }], next: null, previous: "previous" });
    if (path === "/admin/accessible-events/?page=1&makerspace_id=1") return Promise.resolve({ results: [{ id: 32, title: "Other event" }], next: null, previous: null });
    if (path === "/admin/events/32/registrations/?page=1") return Promise.resolve({ results: [{ id: 3, name: "Other participant" }], next: null, previous: null });
    throw new Error(`Unexpected route ${path}`);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(view(client, 1, 1, ["events"], ["accept_request", "manage_events"]));
  await screen.findByText("Event #31");
  fireEvent.click(screen.getByRole("button", { name: "Edit or remove" }));
  await screen.findByRole("button", { name: "First" });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  await screen.findByRole("button", { name: "Second" });
  fireEvent.click(screen.getByRole("button", { name: "Choose a different resource" }));
  fireEvent.click(await screen.findByRole("button", { name: "Other event" }));
  fireEvent.click(await screen.findByRole("button", { name: "Other participant" }));
  expect(screen.getByRole("button", { name: "Other participant" })).toHaveAttribute("aria-pressed", "true");
  expect(mocks.request).toHaveBeenCalledWith("/admin/events/32/registrations/?page=1");
  expect(mocks.request).not.toHaveBeenCalledWith("/admin/events/32/registrations/?page=2");
});

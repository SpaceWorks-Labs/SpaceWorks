import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { ContextualRequest } from "./ContextualRequest";
import { PendingIntake, type SelfBody } from "./contextualIntake";
const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: mock.request, staffRequest: vi.fn() }));

it("sends selected owner event and booking together and retries unchanged after failure", async () => {
  const booking = "22222222-2222-4222-8222-222222222222";
  let submissions = 0; mock.request.mockReset();
  mock.request.mockImplementation((path: string) => {
    if (path.includes("event-history")) return Promise.resolve({ registrations: [{ registration_id: 3, status: "registered", event: { title: "Workshop" } }] });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    if (path.includes("my-bookings")) return Promise.resolve({ results: [{ public_token: booking, status: "confirmed", space_name: "Room", starts_at: "2030-01-01T10:00:00Z" }], next: null });
    if (path.endsWith("/requests/contextual")) { submissions++; return submissions === 1 ? Promise.reject(new Error("offline")) : Promise.resolve({ kind: "request", public_token: "token", status: "pending_approval", replayed: true }); }
    throw new Error(`Unexpected route ${path}`);
  });
  const complete = vi.fn(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ContextualRequest scope="person:1:forge" slug="forge" makerspaceId={1} eventsEnabled bookingsEnabled fields={{ items: [{ product_id: 2, quantity: 1 }], requested_for: "Build" }} canSubmit admitted={() => true} pendingOwner={new PendingIntake()} onLock={vi.fn()} onDenied={vi.fn()} onComplete={complete} /></QueryClientProvider>);
  await screen.findByRole("option", { name: "Workshop" });
  await screen.findByRole("option", { name: /Room/ });
  fireEvent.change(screen.getByLabelText("Your event"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("Your booking"), { target: { value: booking } });
  fireEvent.click(screen.getByRole("button", { name: "Submit equipment request" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry the same request" }));
  await waitFor(() => expect(complete).toHaveBeenCalledTimes(1));
  const calls = mock.request.mock.calls.filter(call => String(call[0]).endsWith("/requests/contextual"));
  expect(calls).toHaveLength(2); expect(calls[0][1].body).toBe(calls[1][1].body);
  expect(JSON.parse(calls[0][1].body)).toMatchObject({ event_registration_id: 3, booking_token: booking });
});

it.each([
  { label: "ordinary", event: null, booking: null },
  { label: "event only", event: 3, booking: null },
  { label: "booking only", event: null, booking: "22222222-2222-4222-8222-222222222222" },
])("sends the exact $label context without inventing the other", async ({ event, booking }) => {
  const token = "22222222-2222-4222-8222-222222222222";
  mock.request.mockReset(); mock.request.mockImplementation((path: string) => {
    if (path.includes("event-history")) return Promise.resolve({ registrations: [{ registration_id: 3, status: "registered", event: { title: "Workshop" } }] });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    if (path.includes("my-bookings")) return Promise.resolve({ results: [{ public_token: token, status: "confirmed", space_name: "Room", starts_at: "2030-01-01T10:00:00Z" }], next: null, previous: null });
    if (path.endsWith("/requests/contextual")) return Promise.resolve({ kind: "request", public_token: "token", status: "pending_approval", replayed: false });
    throw new Error(`Unexpected route ${path}`);
  });
  const done = vi.fn(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ContextualRequest scope="person:1:forge" slug="forge" makerspaceId={1} eventsEnabled bookingsEnabled fields={{ items: [{ product_id: 2, quantity: 1 }], requested_for: "Build" }} canSubmit admitted={() => true} pendingOwner={new PendingIntake()} onLock={vi.fn()} onDenied={vi.fn()} onComplete={done} /></QueryClientProvider>);
  await screen.findByRole("option", { name: "Workshop" });
  await screen.findByRole("option", { name: /Room/ });
  if (event) fireEvent.change(screen.getByLabelText("Your event"), { target: { value: String(event) } });
  if (booking) fireEvent.change(screen.getByLabelText("Your booking"), { target: { value: booking } });
  fireEvent.click(screen.getByRole("button", { name: "Submit equipment request" }));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  const call = mock.request.mock.calls.find(row => String(row[0]).endsWith("/requests/contextual"));
  expect(JSON.parse(call![1].body)).toMatchObject({ event_registration_id: event, booking_token: booking });
});


it("retains an uncertain intent across sheet unmount and retries its exact UUID", async () => {
  const owner = new PendingIntake<SelfBody>();
  mock.request.mockReset(); mock.request.mockImplementation((path: string) => {
    if (path.includes("event-history")) return Promise.resolve({ registrations: [{ registration_id: 3, status: "registered", event: { title: "Workshop" } }] });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    if (path.endsWith("/requests/contextual")) return Promise.reject(new Error("offline"));
    throw new Error(`Unexpected route ${path}`);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = () => <QueryClientProvider client={client}><ContextualRequest scope="person:1:forge" slug="forge" makerspaceId={1} eventsEnabled bookingsEnabled={false} fields={{ items: [{ product_id: 2, quantity: 1 }], requested_for: "Build" }} canSubmit admitted={() => true} pendingOwner={owner} onLock={vi.fn()} onDenied={vi.fn()} onComplete={vi.fn()} /></QueryClientProvider>;
  const first = render(ui()); await screen.findByRole("option", { name: "Workshop" });
  fireEvent.change(screen.getByLabelText("Your event"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit equipment request" }));
  await screen.findByRole("button", { name: "Retry the same request" });
  const original = mock.request.mock.calls.find(call => String(call[0]).endsWith("/requests/contextual"))?.[1].body;
  first.unmount(); render(ui()); fireEvent.click(screen.getByRole("button", { name: "Retry the same request" }));
  await waitFor(() => expect(mock.request.mock.calls.filter(call => String(call[0]).endsWith("/requests/contextual"))).toHaveLength(2));
  const calls = mock.request.mock.calls.filter(call => String(call[0]).endsWith("/requests/contextual"));
  expect(calls[1][1].body).toBe(original);
});


it("never replays a retained request after actor scope changes", async () => {
  const owner = new PendingIntake<SelfBody>();
  owner.begin("person:1:forge", { operation_id: "11111111-1111-4111-8111-111111111111", event_registration_id: 3, booking_token: null, items: [{ product_id: 2, quantity: 1 }], requested_for: "Build" });
  mock.request.mockReset(); mock.request.mockResolvedValue({ results: [], next: null, previous: null });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ContextualRequest scope="person:2:forge" slug="forge" makerspaceId={1} eventsEnabled={false} bookingsEnabled={false} fields={{ items: [{ product_id: 2, quantity: 1 }], requested_for: "Build" }} canSubmit admitted={() => true} pendingOwner={owner} onLock={vi.fn()} onDenied={vi.fn()} onComplete={vi.fn()} /></QueryClientProvider>);
  expect(screen.queryByRole("button", { name: "Retry the same request" })).toBeNull();
  expect(owner.current("person:1:forge")).toBeUndefined();
  expect(mock.request.mock.calls.some(call => String(call[0]).endsWith("/requests/contextual"))).toBe(false);
});

it("keeps an uncertain operation locked when a later retry is denied", async () => {
  const owner = new PendingIntake<SelfBody>();
  const locked = vi.fn(); const denied = vi.fn(); let attempts = 0;
  mock.request.mockReset(); mock.request.mockImplementation((path: string) => {
    if (path.includes("event-history")) return Promise.resolve({ registrations: [{ registration_id: 3, status: "registered", event: { title: "Workshop" } }] });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    if (path.endsWith("/requests/contextual")) { attempts++; return Promise.reject(attempts === 1 ? new Error("offline") : Object.assign(new Error("denied"), { status: 403 })); }
    throw new Error(`Unexpected route ${path}`);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ContextualRequest scope="person:1:forge" slug="forge" makerspaceId={1} eventsEnabled bookingsEnabled={false} fields={{ items: [{ product_id: 2, quantity: 1 }], requested_for: "Build" }} canSubmit admitted={() => true} pendingOwner={owner} onLock={locked} onDenied={denied} onComplete={vi.fn()} /></QueryClientProvider>);
  await screen.findByRole("option", { name: "Workshop" });
  fireEvent.change(screen.getByLabelText("Your event"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit equipment request" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry the same request" }));
  await screen.findByText("This request is unavailable for your access.");
  expect(owner.current("person:1:forge")).toBeDefined();
  expect(locked).toHaveBeenCalledTimes(1); expect(denied).not.toHaveBeenCalled();
  expect(screen.queryByText("Workshop")).toBeNull();
});

it("releases a first definitive validation failure for correction", async () => {
  const owner = new PendingIntake<SelfBody>(); const denied = vi.fn();
  mock.request.mockReset(); mock.request.mockImplementation((path: string) => {
    if (path.includes("event-history")) return Promise.resolve({ registrations: [{ registration_id: 3, status: "registered", event: { title: "Workshop" } }] });
    if (path.includes("equipment-kits")) return Promise.resolve({ results: [], next: null, previous: null });
    return Promise.reject(Object.assign(new Error("invalid"), { status: 400 }));
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ContextualRequest scope="person:1:forge" slug="forge" makerspaceId={1} eventsEnabled bookingsEnabled={false} fields={{ items: [{ product_id: 2, quantity: 1 }], requested_for: "Build" }} canSubmit admitted={() => true} pendingOwner={owner} onLock={vi.fn()} onDenied={denied} onComplete={vi.fn()} /></QueryClientProvider>);
  await screen.findByRole("option", { name: "Workshop" });
  fireEvent.change(screen.getByLabelText("Your event"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit equipment request" }));
  await screen.findByText("Check your request and try again.");
  expect(owner.current("person:1:forge")).toBeUndefined(); expect(denied).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Submit equipment request" })).toBeEnabled();
});

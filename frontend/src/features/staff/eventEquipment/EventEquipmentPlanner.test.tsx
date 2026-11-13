import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StaffListContext } from "../StaffListContext";
import { EventEquipmentPlanner } from "./EventEquipmentPlanner";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest }));

const base = "/admin/makerspace/3/events/9";
const people = [
  { id: 101, name: "Asha", status: "registered" },
  { id: 102, name: "Ben", status: "attended" },
  { id: 103, name: "Cleo", status: "waitlisted" },
];
const availability = {
  window: { starts_at: "2026-12-01T09:00:00Z", return_due_at: "2026-12-01T19:00:00Z" }, equipment_return_hours: 2, counts_visible: true,
  results: [
    { product_id: 5, name: "Soldering iron", event_only: false, status: "available", free: 6, committed: 2 },
    { product_id: 6, name: "Oscilloscope", event_only: true, status: "limited", free: 1, committed: 3 },
  ],
};
const posts: Record<string, unknown>[] = [];

function show({ modules = ["events", "request_workflow", "staff_admin"], features = ["loans.enabled"], canEditWindow = false } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 1, makerspace: { id: 3, enabled_modules: modules, enabled_features: features } }}>
      <EventEquipmentPlanner makerspaceId={3} eventId={9} participants={people} canEditWindow={canEditWindow} />
    </StaffListContext.Provider>
  </QueryClientProvider>);
  return invalidate;
}

beforeEach(() => {
  posts.length = 0;
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === `${base}/equipment-request-products?page=1`) return { results: [{ id: 5, name: "Soldering iron" }, { id: 6, name: "Oscilloscope", event_only: true }], next: null, previous: null };
    if (path === `${base}/equipment-availability?product_ids=5,6`) return availability;
    if (path === `${base}/equipment-plan`) {
      const body = JSON.parse(String(init?.body)); posts.push(body);
      return body.dry_run
        ? { dry_run: true, totals: [{ product_id: 5, requested: 2, status: "ok", free: 6 }, { product_id: 6, requested: 2, status: "short", free: 1 }], results: [] }
        : { dry_run: false, totals: [], results: [
          { registration_id: 101, outcome: "created", request_id: 501, status: "pending_approval" },
          { registration_id: 102, outcome: "error", code: "lock_busy" }] };
    }
    throw new Error(`Unexpected ${path}`);
  });
});

it("stays away when lending or events are switched off", () => {
  show({ features: [] });
  expect(screen.queryByRole("button", { name: "Plan equipment for several people" })).toBeNull();
});

it("shows window availability with the events-only badge and counts", async () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "Plan equipment for several people" }));
  expect(await screen.findByText(/Availability from/)).toHaveTextContent("Items are due 2 hours after the event ends.");
  expect(screen.getByText("Events only")).toBeInTheDocument();
  expect(screen.getByText("Free for the event")).toBeInTheDocument();
  expect(screen.getByText("Limited during the event")).toBeInTheDocument();
  expect(screen.getByText("1 free for the whole window · 3 committed")).toBeInTheDocument();
  // Only registered or attended people can be planned for.
  const group = screen.getByRole("group", { name: "People on this page" });
  expect(within(group).queryByText("Cleo")).toBeNull();
});

it("previews with a dry run, then creates one request per person and reports each", async () => {
  const invalidate = show();
  fireEvent.click(screen.getByRole("button", { name: "Plan equipment for several people" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Soldering iron" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Oscilloscope" }));
  fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity of Soldering iron per person" }), { target: { value: "1" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Everyone listed" }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop kits" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview plan" }));
  expect(await screen.findByText("Short")).toBeInTheDocument();
  expect(posts[0]).toMatchObject({ dry_run: true, requested_for: "Workshop kits",
    lines: [{ product_id: 5, quantity: 1 }, { product_id: 6, quantity: 1 }], participants: [{ registration_id: 101 }, { registration_id: 102 }] });
  expect(invalidate).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "Create 2 requests" }));
  expect(await screen.findByText(/Request #501 created/)).toBeInTheDocument();
  expect(screen.getByText(/system was busy/)).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("1 of 2 could not be created");
  expect(posts[1]).toMatchObject({ dry_run: false });
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["event-equipment-desk", 3, 9] }));

  // Retrying reuses the same operation id, so created rows replay instead of duplicating.
  fireEvent.click(screen.getByRole("button", { name: "Retry failed" }));
  await waitFor(() => expect(posts).toHaveLength(3));
  expect(posts[2].operation_id).toBe(posts[1].operation_id);
});

it("sends a per-person line override while everyone else keeps the default lines", async () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "Plan equipment for several people" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Soldering iron" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Oscilloscope" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Everyone listed" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Different items for Asha" }));
  fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity of Oscilloscope for Asha" }), { target: { value: "3" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity of Soldering iron for Asha" }), { target: { value: "0" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview plan" }));
  await screen.findByText("Short");
  expect(posts[0]).toMatchObject({ lines: [{ product_id: 5, quantity: 1 }, { product_id: 6, quantity: 1 }],
    participants: [{ registration_id: 101, lines: [{ product_id: 6, quantity: 3 }] }, { registration_id: 102 }] });
  expect(posts[0].participants).toEqual([{ registration_id: 101, lines: [{ product_id: 6, quantity: 3 }] }, { registration_id: 102 }]);
});

it("will not preview a person whose override leaves them nothing", async () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "Plan equipment for several people" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Soldering iron" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Asha" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Different items for Asha" }));
  fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity of Soldering iron for Asha" }), { target: { value: "0" } });
  expect(screen.getByRole("alert")).toHaveTextContent("Give Asha at least one item");
  expect(screen.getByRole("button", { name: "Preview plan" })).toBeDisabled();
});

it("lets an event editor set the return window from the planner", async () => {
  show({ canEditWindow: true });
  fireEvent.click(screen.getByRole("button", { name: "Plan equipment for several people" }));
  expect(await screen.findByLabelText(/Items due N hours after the event ends/)).toHaveValue(2);
});

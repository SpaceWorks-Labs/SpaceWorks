import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BookingDrawer } from "./BookingDrawer";
import { getStaffAccess } from "./staffAccess";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));
const resource = { id: 8, makerspace_id: 3, name: "Workshop", description: "Resource description", is_active: true,
  kind: "bench", location: "Upstairs", capacity: 3, custom_form: null, updated_at: "2026-10-15T10:00:00Z",
  can_manage_grants: false, staff_grants_enabled: true, recurring_enabled: true, staff_permissions: ["check_in"] };
function setup(permissions = ["check_in"]) {
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "PATCH") return { ...resource, staff_permissions: permissions };
    if (path === "/admin/spaces/8/") return { ...resource, staff_permissions: permissions };
    if (path.includes("eligible-members")) return { results: [] };
    if (path.includes("bookings/?")) return { count: 0, results: [], previous: null, next: null };
    throw new Error("Unexpected private request: " + path);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<MemoryRouter><QueryClientProvider client={client}><BookingDrawer makerspaceId={3} spaceId={8} onClose={() => {}} /></QueryClientProvider></MemoryRouter>);
}

describe("booking resource authority UI", () => {
  beforeEach(() => { request.mockReset(); });
  it("booking-only and mixed grants use one narrow workspace", () => {
    expect(getStaffAccess([], false, true, false, false, true).allowedTabs).toEqual(["granted"]);
    expect(getStaffAccess([], false, true, false, true, true).allowedTabs).toEqual(["granted"]);
    expect(getStaffAccess([], false, true, false, false, true).canManageBookings).toBe(false);
  });
  it("a scanner never loads roster or payment data or exposes editing controls", async () => {
    setup(); await screen.findByText("Resource description");
    expect(request.mock.calls.map(([path]) => path)).toEqual(["/admin/spaces/8/"]);
    expect(screen.queryByText("This space is inactive and read-only.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deactivate space" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save details" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Staff access" })).not.toBeInTheDocument();
  });
  it("descriptive edits submit only descriptive fields and never request machine choices", async () => {
    setup(["edit_details"]); await screen.findByRole("button", { name: "Save details" });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "New description" } });
    fireEvent.click(screen.getByRole("button", { name: "Save details" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/spaces/8/", expect.objectContaining({ method: "PATCH" })));
    const call = request.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(Object.keys(JSON.parse(call![1].body)).sort()).toEqual(["capacity", "custom_form", "description", "kind", "location", "name"]);
    expect(request.mock.calls.some(([path]) => path.includes("machine-types") || path.includes("bookings/?"))).toBe(false);
  });
  it("reservation staff get recurrence but no grant or finance controls", async () => {
    setup(["manage_reservations"]);
    await waitFor(() => expect(request.mock.calls.some(([path]) => path.includes("bookings/?"))).toBe(true));
    // The booking form (with its recurrence option) opens in the New booking dialog.
    fireEvent.click(await screen.findByRole("button", { name: "New booking" }));
    expect(await screen.findByLabelText("Repeat weekly in makerspace local time")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Invite staff" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deactivate space" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Description")).not.toBeInTheDocument();
  });
});

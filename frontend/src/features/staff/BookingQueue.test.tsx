import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest }));
vi.mock("./useDomainSettingsDialog", () => ({ useDomainSettingsDialog: () => ({ actions: [], dialog: null }) }));
vi.mock("./ListViewControls", () => ({ ListViewControls: () => null }));
vi.mock("./quickCreate", () => ({ useQuickCreate: () => undefined }));

import { BookingsPanel } from "./BookingsPanel";
import { BookingIssuesList } from "./BookingIssuesList";

const pending = { id: 41, space_id: 4, space_name: "Laser bench", name: "Ada", email: "ada@example.test", phone: "1",
  starts_at: "2026-11-01T10:00:00Z", ends_at: "2026-11-01T11:00:00Z", status: "pending", custom_answers: null, payment: null };
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function renderPanel(entry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry]}>
    <BookingsPanel makerspaceId={7} /><Location />
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.startsWith("/admin/makerspaces/7/bookings/")) return page(path.includes("status=pending") ? [pending] : []);
    if (path.startsWith("/admin/makerspaces/7/booking-issues/")) return { ...page([]), open_count: 2 };
    if (path.startsWith("/admin/makerspaces/7/spaces/")) return page([]);
    if (path === "/admin/bookings/41/reject/") return { ...pending, status: "rejected", decision_reason: JSON.parse(String(init?.body)).reason };
    if (path === "/admin/bookings/41/approve/") return { ...pending, status: "confirmed" };
    throw new Error("unexpected " + path);
  });
});

describe("Bookings Requests queue", () => {
  it("lands on the cross-space Requests queue and shows the open issue count", async () => {
    renderPanel("/admin/bookings");
    expect(await screen.findByText("Ada")).toBeInTheDocument();
    expect(screen.getByText(/Laser bench/)).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith(expect.stringContaining("/admin/makerspaces/7/bookings/?status=pending"));
    await waitFor(() => expect(screen.getByRole("tab", { name: /Issues/ })).toHaveTextContent("2"));
  });

  it("keeps the dashboard status filter instead of dropping it", async () => {
    renderPanel("/admin/bookings?status=confirmed");
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(expect.stringContaining("status=confirmed")));
    expect(await screen.findByText("No bookings match this filter.")).toBeInTheDocument();
  });

  it("rejects only with a reason and sends it", async () => {
    renderPanel("/admin/bookings");
    fireEvent.click(await screen.findByRole("button", { name: "More actions for Ada" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Reject with reason" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Reject booking request" }));
    expect(within(dialog).getByText(/Add a reason/)).toBeInTheDocument();
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/bookings/41/reject/", expect.anything());
    fireEvent.change(within(dialog).getByLabelText(/Reason \(required\)/), { target: { value: "Closed that day" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Reject booking request" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/bookings/41/reject/",
      expect.objectContaining({ body: JSON.stringify({ reason: "Closed that day" }) })));
  });

  it("opens a request in its space with the booking selected", async () => {
    renderPanel("/admin/bookings");
    fireEvent.click(await screen.findByRole("button", { name: "More actions for Ada" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Open in space" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("space=4"));
    expect(screen.getByTestId("location")).toHaveTextContent("booking=41");
  });
});

describe("Booking issues list", () => {
  it("resolves an open issue with an optional note", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path.startsWith("/admin/makerspaces/7/booking-issues/")) return { ...page([{ id: 3, booking_id: 41, space_id: 4,
        space_name: "Laser bench", booker_name: "Ada", starts_at: pending.starts_at, ends_at: pending.ends_at, outcome: "damaged",
        remark: "Vice cracked", source: "member", created_at: pending.starts_at, resolved_at: null, resolution_note: "" }]), open_count: 1 };
      if (path === "/admin/booking-issues/3/resolve/") return {};
      throw new Error("unexpected " + path);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><BookingIssuesList makerspaceId={7} /></QueryClientProvider>);
    expect(await screen.findByText("“Vice cracked”")).toBeInTheDocument();
    expect(screen.getByText(/Something was damaged · Ada/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    fireEvent.change(screen.getByLabelText(/What was done/), { target: { value: "Replaced" } });
    fireEvent.click(screen.getByRole("button", { name: "Mark resolved" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/booking-issues/3/resolve/",
      expect.objectContaining({ body: JSON.stringify({ note: "Replaced" }) })));
  });
});

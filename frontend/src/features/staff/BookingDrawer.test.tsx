import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { BookingDrawer } from "./BookingDrawer";
const { useSpaceBookings } = vi.hoisted(() => ({ useSpaceBookings: vi.fn() }));
vi.mock("./bookingsApi", () => ({
  // A full manager: booking tabs are gated per resource grant (bookingStaffPermissions).
  useBookableSpace: () => ({ data: { id: 4, name: "Bench", location: "Lab", is_active: true, can_manage_grants: true,
    effective_requester_notifications_enabled: false }, isLoading: false, error: null, refetch: vi.fn() }),
  useSpaceBookings, useUpdateBookableSpace: () => ({ error: null, isPending: false, mutate: vi.fn() }),
  useDeactivateBookableSpace: () => ({ error: null, isPending: false, mutate: vi.fn() }),
  useBookingAction: () => ({ error: null, isPending: false, mutate: vi.fn() }),
}));
vi.mock("./PaymentReconcileActions", () => ({ PaymentReconcileActions: () => null }));
vi.mock("./BookableSpaceForm", () => ({ BookableSpaceForm: () => null, valuesForSpace: () => ({}) }));
vi.mock("./StaffBookingForm", () => ({ StaffBookingForm: () => null }));
// Runs its own availability query; the navigation assertions need no QueryClient.
vi.mock("./BookingUnavailableBlocks", () => ({ BookingUnavailableBlocks: () => null }));
// The Calendar tab runs its own upcoming-bookings query (filters carry `starts_at`); assert on the requests list.
const listCall = () => useSpaceBookings.mock.calls.filter(call => !call[1]?.starts_at).at(-1);
function Location() { return <output data-testid="location">{useLocation().search}</output>; }
describe("booking agenda navigation", () => {
  it("opens a page-two booking on page one while preserving the space and unrelated filters", async () => {
    useSpaceBookings.mockReturnValue({ isLoading: false, error: null, refetch: vi.fn(),
      data: { count: 30, next: null, previous: "page1", results: [{ id: 9, name: "Ada",
        starts_at: "2026-11-01T10:00:00Z", ends_at: "2026-11-01T11:00:00Z", status: "confirmed",
        email: "ada@example.test", phone: "123", custom_answers: null, payment: null }] } });
    render(<MemoryRouter initialEntries={["/admin/bookings?space=4&booking-4.page=2&bookingTab=calendar&q=laser"]}>
      <BookingDrawer makerspaceId={7} spaceId={4} onClose={vi.fn()} /><Location />
    </MemoryRouter>);
    expect(listCall()?.[2]).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "Open booking" }));
    await waitFor(() => expect(listCall()?.[2]).toBe(1));
    expect(listCall()?.[1]).toEqual(expect.objectContaining({ booking_id: 9 }));
    expect(screen.getByTestId("location")).toHaveTextContent("q=laser");
    expect(screen.getByTestId("location")).toHaveTextContent("bookingTab=requests");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Show all bookings" }));
    await waitFor(() => expect(listCall()?.[1].booking_id).toBeUndefined());
  });
});

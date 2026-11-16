import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { BookingReservationEditor, canMoveBooking } from "./BookingReservationEditor";
import { BookingCloneControl } from "./BookingCloneControl";
import type { BookableSpace, Booking } from "./bookingsApi";

const { edit, clone } = vi.hoisted(() => ({ edit: vi.fn(), clone: vi.fn() }));
let pending = false;
let error: Error | null = null;
vi.mock("./bookingToolsApi", () => ({
  useEditBooking: () => ({ mutate: edit, reset: vi.fn(), isPending: pending, error }),
  useCloneBookingSpace: () => ({ mutate: clone, isPending: pending, error, data: null }),
}));
const resource = { id: 8, makerspace_id: 3, name: "Workshop", public_token: "resource", kind: "bench", description: "A bench", capacity: 1, location: "Upstairs", image_url: "", is_public: false, show_public_availability: false, show_public_booker_names: false, approval_mode: "instant", payment_amount: "0.00", requester_notifications_enabled: null, effective_requester_notifications_enabled: true, is_active: true, created_by_id: null, created_at: "2026-10-15T00:00:00Z", updated_at: "2026-10-15T00:00:00Z", custom_form: [{ id: "purpose", label: "Purpose", type: "short_text", options: [], required: true }], can_copy_booking_rules: false } as BookableSpace;
const booking = { id: 2, starts_at: "2099-01-01T12:00:00Z", ends_at: "2099-01-01T13:00:00Z", status: "confirmed", note: "Keep safe", custom_answers: { version: 1, answers: [{ id: "purpose", label: "Old label", type: "short_text", value: "Prototype" }] } } as Booking;
beforeEach(() => { edit.mockReset(); clone.mockReset(); pending = false; error = null; });

describe("reservation staff editor", () => {
  it("validates current answers and submits only note and raw answers", async () => {
    const { container } = render(<BookingReservationEditor space={resource} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit note and answers" }));
    expect(screen.getByLabelText(/Purpose/)).toHaveValue("Prototype");
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save reservation details" }));
    expect(edit).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Robot" } });
    fireEvent.change(screen.getByLabelText("Reservation note"), { target: { value: "New note" } });
    fireEvent.click(screen.getByRole("button", { name: "Save reservation details" }));
    expect(edit).toHaveBeenCalledWith({ kind: "details", note: "New note", custom_answers: { purpose: "Robot" } }, expect.any(Object));
    await expectNoA11yViolations(container);
  });
  it.each(["rejected", "cancelled", "completed", "no_show"] as const)("terminal %s never offers a time edit", (status) => {
    render(<BookingReservationEditor space={resource} booking={{ ...booking, status }} />);
    expect(screen.queryByRole("button", { name: "Edit booking time" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit note and answers" })).not.toBeInTheDocument();
  });
  it("hides both editors after arrival and restores them after reversal", () => {
    const { rerender } = render(<BookingReservationEditor space={resource} booking={{ ...booking, arrived_at: "2099-01-01T11:45:00Z" }} />);
    expect(screen.queryByRole("button", { name: "Edit note and answers" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit booking time" })).not.toBeInTheDocument();
    expect(canMoveBooking({ ...booking, arrived_at: "2099-01-01T11:45:00Z" }, 0, 0)).toBe(false);
    rerender(<BookingReservationEditor space={resource} booking={{ ...booking, arrived_at: null }} />);
    expect(screen.getByRole("button", { name: "Edit note and answers" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit booking time" })).toBeInTheDocument();
  });
  it.each(["removed", "new_required", "changed_type"])("saves only the note when the form has %s questions", (change) => {
    const custom_form: BookableSpace["custom_form"] = change === "removed" ? [] : change === "new_required"
      ? [...resource.custom_form!, { id: "new", label: "New required question", type: "short_text", options: [], required: true }]
      : [{ ...resource.custom_form![0], type: "number" }];
    render(<BookingReservationEditor space={{ ...resource, custom_form }} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit note and answers" }));
    // Native required/type validation must also allow an unrelated note edit.
    expect(screen.getByRole("form")).toHaveAttribute("novalidate");
    fireEvent.change(screen.getByLabelText("Reservation note"), { target: { value: "New note" } });
    fireEvent.click(screen.getByRole("button", { name: "Save reservation details" }));
    expect(edit).toHaveBeenCalledWith({ kind: "details", note: "New note" }, expect.any(Object));
    expect(screen.queryByText("This question is required.")).not.toBeInTheDocument();
  });
  it("submits an answer-only edit without the unchanged note", () => {
    render(<BookingReservationEditor space={resource} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit note and answers" }));
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Robot" } });
    fireEvent.click(screen.getByRole("button", { name: "Save reservation details" }));
    expect(edit).toHaveBeenCalledWith({ kind: "details", custom_answers: { purpose: "Robot" } }, expect.any(Object));
  });
  it("does not submit unchanged or reverted fields", () => {
    render(<BookingReservationEditor space={resource} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit note and answers" }));
    const save = screen.getByRole("button", { name: "Save reservation details" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Robot" } });
    expect(save).toBeEnabled();
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Prototype" } });
    expect(save).toBeDisabled();
    fireEvent.submit(screen.getByRole("form"));
    expect(edit).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Reservation note"), { target: { value: "New note" } });
    fireEvent.click(save);
    expect(edit).toHaveBeenCalledWith({ kind: "details", note: "New note" }, expect.any(Object));
  });
  it("validates newly required answers when staff change answers", () => {
    render(<BookingReservationEditor space={{ ...resource, custom_form: [...resource.custom_form!,
      { id: "new", label: "New required question", type: "short_text", options: [], required: true },
    ] }} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit note and answers" }));
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Robot" } });
    fireEvent.click(screen.getByRole("button", { name: "Save reservation details" }));
    expect(edit).not.toHaveBeenCalled();
    expect(screen.getByText("This question is required.")).toBeInTheDocument();
  });
  it("uses a strict old cutoff including equality and started/ended windows", () => {
    const now = new Date(booking.starts_at).getTime() - 3600000;
    expect(canMoveBooking(booking, 1, now)).toBe(false);
    expect(canMoveBooking(booking, 1, now - 1)).toBe(true);
    expect(canMoveBooking(booking, 0, now + 3600000)).toBe(false);
  });
  it("moves with UTC input while displaying server errors", () => {
    error = new Error("This space is already booked for that time.");
    render(<BookingReservationEditor space={resource} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit booking time" }));
    fireEvent.change(screen.getByLabelText("New start (your local time)"), { target: { value: "2099-01-02T14:00" } });
    fireEvent.change(screen.getByLabelText("New end (your local time)"), { target: { value: "2099-01-02T15:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save booking time" }));
    expect(edit).toHaveBeenCalledWith({ kind: "time", starts_at: new Date("2099-01-02T14:00").toISOString(), ends_at: new Date("2099-01-02T15:00").toISOString() }, expect.any(Object));
    expect(screen.getByRole("alert")).toHaveTextContent("already booked");
  });
  it("shows the fresh preview on 409 price_changed and resends the digest", async () => {
    const { StructuredApiError } = await import("../../lib/api");
    const preview = { charges: "tracked", quote: { total: "12.00", currency: "USD", discount_total: "0.00" }, price_confirmation: "digest-1" };
    edit.mockImplementationOnce((_vars: unknown, options: { onError: (e: unknown) => void }) => options.onError(
      new StructuredApiError(409, { code: "price_changed", confirmation: preview } as never)));
    render(<BookingReservationEditor space={resource} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit booking time" }));
    fireEvent.change(screen.getByLabelText("New start (your local time)"), { target: { value: "2099-01-02T14:00" } });
    fireEvent.change(screen.getByLabelText("New end (your local time)"), { target: { value: "2099-01-02T15:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Save booking time" }));
    expect(edit.mock.calls[0][0]).not.toHaveProperty("price_confirmation");
    expect(await screen.findByText(/Room price/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm price and save time" }));
    expect(edit.mock.calls[1][0]).toMatchObject({ kind: "time", price_confirmation: "digest-1" });
  });
  it("does not submit when keeping the current booking", () => {
    render(<BookingReservationEditor space={resource} booking={booking} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit booking time" }));
    fireEvent.click(screen.getByRole("button", { name: "Keep current booking" }));
    expect(edit).not.toHaveBeenCalled();
    expect(screen.queryByRole("form")).not.toBeInTheDocument();
  });
});

describe("resource clone", () => {
  it("defaults to ordinary rules and hides the protected option", async () => {
    const { container } = render(<BookingCloneControl space={resource} />);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create private copy" }));
    expect(clone).toHaveBeenCalledWith(false);
    await expectNoA11yViolations(container);
  });
  it("supports an explicitly authorized rules copy", () => {
    render(<BookingCloneControl space={{ ...resource, can_copy_booking_rules: true }} />);
    fireEvent.click(screen.getByLabelText("Copy booking rules"));
    fireEvent.click(screen.getByRole("button", { name: "Create private copy" }));
    expect(clone).toHaveBeenCalledWith(true);
  });
  it("disables pending clone and displays failure", () => {
    pending = true; error = new Error("Storage is unavailable");
    render(<BookingCloneControl space={resource} />);
    expect(screen.getByRole("button", { name: "Cloning..." })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Storage is unavailable");
  });
});

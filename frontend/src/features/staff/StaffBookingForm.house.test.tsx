import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StaffBookingForm } from "./StaffBookingForm";
import type { BookableSpace } from "./bookingsApi";

const { create, previewPrice } = vi.hoisted(() => ({ create: vi.fn(), previewPrice: vi.fn() }));
vi.mock("./staffBookingApi", () => ({
  useBookingEligibleMembers: () => ({ data: { results: [{ member_id: 8, display_name: "Ada" }], next: null, previous: null }, isLoading: false, error: null }),
  useStaffCreateBooking: () => ({ mutate: create, isPending: false, isSuccess: false, error: null }),
  previewStaffBookingPrice: previewPrice,
}));
vi.mock("./StaffBookingAvailability", () => ({ StaffBookingAvailability: () => null, toLocalInput: () => "" }));
vi.mock("./BookingReadiness", () => ({ StaffBookingReadiness: () => null }));

const space = { id: 4, makerspace_id: 2, machine_type: 9, custom_form: null } as BookableSpace;

beforeEach(() => { create.mockReset(); previewPrice.mockReset(); });

it("creates a house booking with no member, no price review and no certification override", () => {
  render(<StaffBookingForm makerspaceId={2} space={space} recurringEnabled />);
  fireEvent.click(screen.getByRole("checkbox", { name: "House booking (no member, no charge)" }));
  expect(screen.queryByRole("combobox", { name: "Member" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Certification override reason/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Repeat weekly/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Starts (your local time)"), { target: { value: "2026-11-01T14:00" } });
  fireEvent.change(screen.getByLabelText("Ends (your local time)"), { target: { value: "2026-11-01T15:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Create house booking" }));
  expect(previewPrice).not.toHaveBeenCalled();
  expect(create).toHaveBeenCalledWith({
    starts_at: new Date("2026-11-01T14:00").toISOString(), ends_at: new Date("2026-11-01T15:00").toISOString(),
    note: "", house: true,
  }, expect.anything());
});

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { BookingPassPrint } from "./BookingPassPrint";
import { BookingArrivalScanner } from "./BookingArrivalScanner";

const { print, mutation, staff } = vi.hoisted(() => ({ print: vi.fn(), mutation: vi.fn(), staff: vi.fn() }));
vi.mock("./bookingPassApi", () => ({ usePrintBookingPass: print }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }), useMutation: mutation }));
vi.mock("../../lib/api", () => ({ staffRequest: staff }));
vi.mock("../../components/ui/QrScanner", () => ({ default: () => null }));

beforeEach(() => {
  print.mockReset(); mutation.mockReset();
  print.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });
});

it("shows rendering and permission errors and disables duplicate print", () => {
  print.mockReturnValueOnce({ mutate: vi.fn(), isPending: true, error: null });
  const { rerender } = render(<BookingPassPrint spaceId={9} bookingId={12} />);
  expect(screen.getByRole("button", { name: "Rendering pass..." })).toBeDisabled();
  print.mockReturnValueOnce({ mutate: vi.fn(), isPending: false, error: new Error("Arrival reversed") });
  rerender(<BookingPassPrint spaceId={9} bookingId={12} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Arrival reversed");
});

it.each([false, true])("scanner offers print only when server projection allows it: %s", (canPrint) => {
  const result = { booking_id: 12, display_name: "Booker", space_name: "Room", timezone: "UTC",
    starts_at: "2030-01-01T10:00:00Z", ends_at: "2030-01-01T11:00:00Z", status: "confirmed",
    arrived_at: canPrint ? "2030-01-01T10:00:00Z" : null, waiver_state: "not_required", can_print_pass: canPrint };
  mutation.mockImplementation((options) => ({ mutate: () => options.onSuccess?.(result), reset: vi.fn(), isPending: false, error: null }));
  render(<BookingArrivalScanner makerspaceId={3} spaceId={9} />);
  fireEvent.change(screen.getByRole("searchbox", { name: "Booking QR" }), { target: { value: "spaceworks-booking:private" } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  expect(Boolean(screen.queryByRole("button", { name: "Print booking pass" }))).toBe(canPrint);
});

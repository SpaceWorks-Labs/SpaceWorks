import { render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { BookingResourceAnalytics } from "./BookingResourceAnalytics";

const { useReports } = vi.hoisted(() => ({ useReports: vi.fn() }));
vi.mock("./bookingReportsApi", () => ({ useBookingResourceReports: useReports }));
vi.mock("./panels/OperationsReportsBookings", () => ({
  BookingUtilizationSummary: () => <section aria-label="Reservation utilization">Reserved hours: 3.50</section>,
}));

beforeEach(() => {
  useReports.mockReturnValue({
    query: { isLoading: false, error: null, data: {
      typed_rows: [{ arrived_reservations: 2, confirmed_without_recorded_arrival: 1 }],
      meta: { arrival_counts_available: true },
    } },
    download: { mutate: vi.fn(), isPending: false, error: null }, validPeriod: true,
  });
});

it("labels recorded arrivals separately from reservation utilization", () => {
  render(<BookingResourceAnalytics makerspaceId={3} spaceId={8} features={["analytics"]} />);
  expect(useReports).toHaveBeenCalledWith(3, 8, "", "", true);
  expect(screen.getByRole("region", { name: "Reservation utilization" })).toHaveTextContent("Reserved hours: 3.50");
  const arrivals = screen.getByRole("region", { name: "Recorded booking arrivals" });
  expect(within(arrivals).getByText("Arrived reservations").parentElement).toHaveTextContent("2");
  expect(within(arrivals).getByText("Confirmed without recorded arrival").parentElement).toHaveTextContent("1");
  expect(arrivals).toHaveTextContent("do not measure physical use or reservation hours");
});

it("does not invent zero arrival counts when the projection is unavailable", () => {
  useReports.mockReturnValueOnce({
    query: { isLoading: false, error: null, data: { typed_rows: [{}], meta: { arrival_counts_available: false } } },
    download: { mutate: vi.fn(), isPending: false, error: null }, validPeriod: true,
  });
  render(<BookingResourceAnalytics makerspaceId={3} spaceId={8} features={["analytics"]} />);
  expect(screen.queryByRole("region", { name: "Recorded booking arrivals" })).not.toBeInTheDocument();
});

import { render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { AvailabilityCalendar } from "./AvailabilityCalendar";
import { usePublicAvailability } from "./publicBookingsApi";

vi.mock("./publicBookingsApi", () => ({ usePublicAvailability: vi.fn() }));

beforeEach(() => {
  vi.mocked(usePublicAvailability).mockReturnValue({ data: {
    public_token: "bench", starts_at: "2026-10-16T00:00:00Z", ends_at: "2026-10-30T00:00:00Z", timezone: "UTC", opening_intervals: [],
    availability: [
      { starts_at: "2026-10-16T10:00:00Z", ends_at: "2026-10-16T12:00:00Z", booker_name: "Asha" },
      { starts_at: "2026-10-17T10:00:00Z", ends_at: "2026-10-17T12:00:00Z", booker_name: null, tentative: true },
    ],
  }, isLoading: false, error: null } as unknown as ReturnType<typeof usePublicAvailability>);
});

it("shows a pending event hold as Tentative with no name, beside a named confirmed booking", () => {
  render(<AvailabilityCalendar makerspaceSlug="lab" publicToken="bench" />);
  const rows = screen.getAllByRole("listitem");
  expect(rows).toHaveLength(2);
  expect(within(rows[0]).getByText("Asha")).toBeInTheDocument();
  expect(within(rows[1]).getByText("Tentative")).toBeInTheDocument();
  expect(rows[1].className).toContain("bg-warn-soft");
  expect(within(rows[1]).queryByText("Asha")).toBeNull();
});

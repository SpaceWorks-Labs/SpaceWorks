import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AvailabilityCalendar } from "./AvailabilityCalendar";
import { EventVenueBlock } from "./EventVenueBlock";

vi.mock("./publicBookingsApi", () => ({
  usePublicAvailability: () => ({
    isLoading: false, error: null, refetch: vi.fn(),
    data: {
      public_token: "room", starts_at: "2026-11-12T00:00:00Z", ends_at: "2026-11-26T00:00:00Z", timezone: "UTC",
      opening_intervals: [{ starts_at: "2026-11-12T09:00:00Z", ends_at: "2026-11-12T17:00:00Z" }],
      availability: [],
      unavailable: [
        { starts_at: "2026-11-12T00:00:00Z", ends_at: "2026-11-12T09:00:00Z", kind: "closed" },
        { starts_at: "2026-11-13T09:00:00Z", ends_at: "2026-11-13T17:00:00Z", kind: "unavailable" },
      ],
    },
  }),
}));

describe("busy overlay on public pages", () => {
  it("lists unavailable time without detail and leaves closed time to the opening hours", () => {
    render(<AvailabilityCalendar makerspaceSlug="north" publicToken="room" />);
    const list = screen.getByRole("list", { name: "Unavailable times" });
    expect(list.querySelectorAll("li")).toHaveLength(1);
    expect(list).toHaveTextContent("Unavailable");
  });

  it("shows only a neutral venue-update notice on the event page", () => {
    const host = { name: "North Lab", slug: "north", location: "", map_url: "", logo_url: "" };
    const space = { public_token: "abc", name: "Main Hall", kind: "meeting", location: "", capacity: 40 };
    const { rerender } = render(<MemoryRouter><EventVenueBlock venue={{ host, space: { ...space, venue_update_pending: false }, photos: [] }} /></MemoryRouter>);
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    rerender(<MemoryRouter><EventVenueBlock venue={{ host, photos: [], space: { ...space, venue_update_pending: true } }} /></MemoryRouter>);
    expect(screen.getByRole("note")).toHaveTextContent("Venue update pending");
  });
});

import { Suspense } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { GrantedResourcesPanel } from "./GrantedResourcesPanel";

const { events, spaces } = vi.hoisted(() => ({ events: vi.fn(), spaces: vi.fn() }));
vi.mock("./eventStaffGrantsApi", () => ({ useAccessibleEvents: events }));
vi.mock("./bookingStaffGrantsApi", () => ({ useAccessibleBookingSpaces: spaces }));
vi.mock("./EventDrawer", () => ({ EventDrawer: () => null }));
vi.mock("./EventSeriesDrawer", () => ({ EventSeriesDrawer: () => null }));
vi.mock("./BookingDrawer", () => ({ BookingDrawer: () => null }));

const grants = [{ event_id: 21, series_id: null, makerspace_id: 8, makerspace_slug: "lab", title: "Granted workshop", source: "event_grant" as const, permissions: ["check_in"] }];
events.mockReturnValue({ data: { count: 1, results: [{ id: 21, makerspace_id: 8, title: "Granted workshop", starts_at: "2026-10-15T10:00:00Z", status: "published", staff_permissions: ["check_in"] }] } });
spaces.mockReturnValue({ data: { count: 1, results: [{ id: 5, makerspace_id: 8, name: "Laser bench", staff_permissions: ["check_in"] }] } });

// Compile the real lazy lists before the assertions' DOM timeout starts.
beforeAll(async () => { await Promise.all([import("./GrantedEventsPanel"), import("./GrantedBookingSpacesPanel")]); });

describe("Assigned resources page", () => {
  it("gives an account with both grant kinds one page heading and a tab per kind", async () => {
    render(<Suspense><GrantedResourcesPanel eventGrants={grants} bookingGrants /></Suspense>);
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Assigned resources" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Granted workshop/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Booking resources" }));
    expect(await screen.findByRole("button", { name: /Laser bench/ })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /Granted workshop/ })).not.toBeInTheDocument();
  });
  it("keeps a single-kind account on that list's own page", async () => {
    render(<Suspense><GrantedResourcesPanel bookingGrants /></Suspense>);
    expect(await screen.findByRole("heading", { level: 1, name: "Assigned booking resources" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  });
});

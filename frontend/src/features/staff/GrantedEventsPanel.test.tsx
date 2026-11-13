import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GrantedEventsPanel } from "./GrantedEventsPanel";
import { getStaffAccess } from "./staffAccess";
import { filterTabsByEnabledModules, staffTabPath } from "./staffTabs";

const { accessible } = vi.hoisted(() => ({ accessible: vi.fn() }));
vi.mock("./eventStaffGrantsApi", () => ({ useAccessibleEvents: accessible }));
// The drawer wrapper reads the host space's features; the panel's routing is the subject here.
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: undefined }) }));
vi.mock("./EventDrawer", () => ({ EventDrawer: ({ eventId }: { eventId: number }) => <p>Opened assigned event {eventId}</p> }));
vi.mock("./EventSeriesDrawer", () => ({ EventSeriesDrawer: ({ seriesId }: { seriesId: number }) => <p>Opened assigned series {seriesId}</p> }));
describe("grant-only console", () => {
  it.each([false, true])("keeps assigned events and central governance on central/single origin (%s)", (single) => {
    const access = getStaffAccess([], false, single, false, true);
    expect(access.allowedTabs).toEqual(single ? ["granted"] : ["granted", "organizations", "organized", "organization-analytics"]);
    expect(access.defaultTab).toBe("granted");
    expect(staffTabPath("granted", false, "maker", single)).toBe("/admin/assigned-events");
  });
  it("allows mixed staff to reach their event grants without inventing actions", () => {
    const access = getStaffAccess(["issue_direct_loan"], false, false, false, true);
    expect(access.allowedTabs).toContain("granted");
    expect(access.canManageEvents).toBe(false);
    expect(access.allowedTabs).not.toContain("inventory");
  });
  it("retains booking assignments without events and hides the tab when both apps are tombstoned", () => {
    expect(filterTabsByEnabledModules(["granted"], { unavailable_apps: ["events"], enabled_modules: [], enabled_features: [] })).toEqual(["granted"]);
    expect(filterTabsByEnabledModules(["granted"], { unavailable_apps: ["events", "bookings"], enabled_modules: [], enabled_features: [] })).toEqual([]);
  });
  it("opens only the server's authorized events", () => {
    accessible.mockReturnValue({ data: { results: [{ id: 21, makerspace_id: 8, title: "Granted workshop", starts_at: "2026-10-15T10:00:00Z", status: "draft", staff_permissions: ["check_in"] }] } });
    render(<GrantedEventsPanel />);
    expect(screen.queryByRole("button", { name: "Create event" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Granted workshop/ }));
    expect(screen.getByText("Opened assigned event 21")).toBeInTheDocument();
  });
  it("shows revocation after the next server response", () => {
    accessible.mockReturnValue({ data: { results: [] } }); render(<GrantedEventsPanel />);
    expect(screen.getByText(/^No assigned events/)).toBeInTheDocument();
  });
  it("opens a series grant even before it has occurrences", () => {
    accessible.mockReturnValue({ data: { results: [] } });
    render(<GrantedEventsPanel grants={[{ event_id: null, series_id: 12, makerspace_id: 8, makerspace_slug: "maker", title: "New series", source: "event_grant", permissions: ["publish_schedule"] }]} />);
    expect(screen.queryByText(/^No assigned events/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /New series/ }));
    expect(screen.getByText("Opened assigned series 12")).toBeInTheDocument();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { SchedulePanel } from "./SchedulePanel";
import { addDays, onDay, stepAnchor, viewWindow, weekStart } from "./scheduleDates";

const { staffRequest, wide } = vi.hoisted(() => ({ staffRequest: vi.fn(), wide: { value: true } }));
vi.mock("../../../lib/api", () => ({ staffRequest }));
vi.mock("../../../components/layouts/useLayoutMedia", () => ({ useLayoutMedia: () => wide.value }));

const makerspace = { id: 7, name: "Forge", slug: "forge", public_code: "forge", telegram_group_chat_id: "", frontend_domain: null,
  hidden_from_central_directory: false, timezone: "UTC" };
const today = new Date().toISOString().slice(0, 10);
const entries = [
  { layer: "bookings", area: "bookings", id: 1, title: "Laser room", starts_at: `${today}T09:00:00Z`, ends_at: `${today}T10:00:00Z`,
    status: "confirmed", link: { tab: "bookings", filters: { booking: "1" } } },
  { layer: "events", area: "events", id: 2, title: "Open night", starts_at: `${today}T18:00:00Z`, ends_at: `${today}T21:00:00Z`,
    status: "published", link: { tab: "events", filters: { event: "2" } } },
];
const mount = (props: Partial<Parameters<typeof SchedulePanel>[0]> = {}) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>
    <SchedulePanel makerspace={makerspace} guestOnly={false} singleTenantLocked={false} groupByArea={false}
      allowedTabs={["bookings", "events", "schedule"]} {...props} />
  </MemoryRouter></QueryClientProvider>);

beforeEach(() => { setRouteSessionContext("person"); staffRequest.mockReset(); wide.value = true; });

describe("schedule dates", () => {
  it("builds view windows within the server's 62-day cap", () => {
    expect(weekStart("2026-11-12")).toBe("2026-11-09");
    expect(viewWindow("week", "2026-11-12")).toEqual({ start: "2026-11-09", end: "2026-11-15" });
    expect(viewWindow("month", "2026-02-10")).toEqual({ start: "2026-02-01", end: "2026-02-28" });
    expect(viewWindow("list", "2026-11-12")).toEqual({ start: "2026-11-12", end: "2026-11-25" });
    expect(stepAnchor("month", "2026-12-15", 1)).toBe("2027-01-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
  });

  it("counts a zero-length maintenance entry on its own day only", () => {
    const entry = { starts_at: "2026-11-12T00:00:00Z", ends_at: "2026-11-12T00:00:00Z" };
    expect(onDay(entry, "2026-11-12", "UTC")).toBe(true);
    expect(onDay(entry, "2026-11-11", "UTC")).toBe(false);
  });
});

describe("decision 242(k): staff Schedule", () => {
  it("loads the week, links each entry to its record and toggles layers on the client", async () => {
    staffRequest.mockResolvedValue({ from: today, to: today, layers: ["bookings", "events"], entries, groups: [] });
    mount();
    expect(await screen.findByRole("link", { name: /Laser room/ })).toHaveAttribute("href", "/m/forge/admin/bookings?booking=1");
    expect(staffRequest.mock.calls[0][0]).toMatch(/^\/admin\/makerspace\/7\/schedule\?start=\d{4}-\d{2}-\d{2}&end=/);
    fireEvent.click(screen.getByRole("checkbox", { name: "Events" }));
    expect(screen.queryByRole("link", { name: /Open night/ })).toBeNull();
    expect(staffRequest).toHaveBeenCalledTimes(1);
  });

  it("groups the list by area for the Space Manager", async () => {
    staffRequest.mockResolvedValue({ from: today, to: today, layers: ["bookings", "events"], entries, groups: [] });
    mount({ groupByArea: true });
    fireEvent.click(await screen.findByRole("radio", { name: "List" }));
    const bookings = await screen.findByRole("region", { name: /Bookings/ });
    expect(within(bookings).getByText("Laser room")).toBeInTheDocument();
  });

  it("offers only day and list views on a phone", async () => {
    wide.value = false;
    staffRequest.mockResolvedValue({ from: today, to: today, layers: ["bookings"], entries: [entries[0]], groups: [] });
    mount();
    expect(await screen.findByText("Laser room")).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "Month" })).toBeNull();
    expect(screen.getByRole("radio", { name: "List" })).toHaveAttribute("aria-checked", "true");
  });

  it("explains an empty schedule for a role with no layers, and offers a retry on error", async () => {
    staffRequest.mockResolvedValueOnce({ from: today, to: today, layers: [], entries: [], groups: [] });
    const view = mount();
    expect(await screen.findByText(/Nothing here is yours to schedule yet/)).toBeInTheDocument();
    view.unmount();
    staffRequest.mockRejectedValue(new Error("boom"));
    mount();
    expect(await screen.findByText(/Couldn't load the schedule/)).toBeInTheDocument();
  });
});

import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { EventAdmin, EventListResponse } from "../organizedEventsApi";
import { OrganizedEventsPanel } from "./OrganizedEventsPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

// The drawer's event-programme panels read their own endpoints and have their own tests.
vi.mock("../eventProgramme", () => ({ EventReadinessPanel: () => null, EventDayPanel: () => null }));
vi.mock("../eventProgramme/EventProgrammePanel", () => ({ EventProgrammePanel: () => null }));
vi.mock("../eventProgramme/EventAddonPanel", () => ({ EventAddonPanel: () => null }));

// Fixture covers the fields this panel reads; the merged EventAdmin type added event-programme fields.
const event = {
  id: 73,
  offline_checkin_enabled: false,
  cancellation_cutoff_hours: null,
  ticketing_features: [],
  registration_audience: "members",
  category_id: null,
  tags: [],
  makerspace_id: 19,
  series_summary: null,
  series_revision: null,
  series_override_fields: [],
  title: "Community repair night",
  description: "Repair together.",
  starts_at: "2026-09-04T12:00:00Z",
  ends_at: "2026-09-04T14:00:00Z",
  timezone_name: "UTC",
  location: "North workshop",
  location_kind: "indoor",
  custom_form: null,
  capacity: 30,
  payment_amount: "0.00",
  registration_requires_approval: false,
  registration_cutoff_at: null,
  registration_cutoff_lead_minutes: null,
  effective_registration_cutoff_at: null,
  registration_open: true,
  is_public: true,
  image_url: null,
  status: "draft",
  created_by_id: 5,
  created_at: "2026-08-20T10:00:00Z",
  updated_at: "2026-08-20T10:00:00Z",
  registration_counts: {
    pending_approval: 0,
    registered: 4,
    attended: 2,
    waitlisted: 1,
    rejected: 0,
    cancelled: 3,
  },
  organizers: [
    { id: 1, name: "Repair Collective", slug: "repair-collective" },
    { id: 2, name: "Open Tools", slug: "open-tools" },
  ],
} as unknown as EventAdmin;

const response = (overrides: Partial<EventListResponse> = {}): EventListResponse => ({
  count: 1,
  next: null,
  previous: null,
  results: [event],
  ...overrides,
});

function mockApi(list = response()) {
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.startsWith("/admin/organized-events/")) return list;
    if (path === `/admin/events/${event.id}/`) {
      if (init?.method === "PATCH") {
        return { ...event, ...JSON.parse(String(init.body)) };
      }
      return event;
    }
    if (path.includes("/registrations/")) {
      return { count: 0, next: null, previous: null, results: [] };
    }
    if (path.endsWith("/collaborators/")) return [];
    return [];
  });
}

function renderPanel(list = response()) {
  mockApi(list);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><OrganizedEventsPanel /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, queryClient };
}

// Braces matter: mockReset() RETURNS the mock, and vitest treats a function returned
// from beforeEach as a teardown callback -- so the concise-arrow form calls staffRequest()
// with no arguments after every test.
beforeEach(() => {
  staffRequest.mockReset();
});

describe("OrganizedEventsPanel", () => {
  it("requests the paginated endpoint with the server page size", async () => {
    renderPanel();

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/organized-events/?page=1&page_size=50",
    ));
  });

  it("renders the layout skeleton while the request is pending", () => {
    staffRequest.mockReturnValue(new Promise(() => {}));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><OrganizedEventsPanel /></MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByLabelText("Loading content")).toBeVisible();
  });

  it("shows a retryable error state", async () => {
    staffRequest.mockRejectedValueOnce(new Error("Network unavailable"));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter><OrganizedEventsPanel /></MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Couldn't load organized events. Try again.")).toBeVisible();
    staffRequest.mockResolvedValueOnce(response({ results: [] }));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
  });

  it("uses the authority-neutral empty state", async () => {
    renderPanel(response({ count: 0, results: [] }));

    expect(await screen.findByText("No organized events. Events your organization runs will appear here.")).toBeVisible();
  });

  it("renders organizer names, slugs, and every registration count", async () => {
    renderPanel();

    expect(await screen.findByText("Repair Collective")).toBeVisible();
    expect(screen.getByText("(repair-collective)")).toBeVisible();
    expect(screen.getByText("Open Tools")).toBeVisible();
    expect(screen.getByText("10 total")).toBeVisible();
    expect(screen.getByText("4 registered · 2 attended")).toBeVisible();
    expect(screen.getByText("1 waitlisted · 3 cancelled")).toBeVisible();
  });

  it("filters Upcoming and Past across every page, not just the loaded one", async () => {
    const future = { ...event, id: 74, title: "Future fair", starts_at: "2099-01-01T10:00:00Z", ends_at: "2099-01-01T12:00:00Z" };
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/organized-events/?page=1&page_size=200") return response({ count: 2, next: "https://api.test/?page=2", results: [event] });
      if (path === "/admin/organized-events/?page=2&page_size=200") return response({ count: 2, results: [future] });
      return response({ count: 2, next: "https://api.test/?page=2", results: [event] });
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><MemoryRouter><OrganizedEventsPanel /></MemoryRouter></QueryClientProvider>);
    await screen.findByText("Community repair night");
    fireEvent.click(screen.getByRole("link", { name: "Upcoming" }));
    expect(await screen.findByText("Future fair")).toBeVisible();
    expect(screen.queryByText("Community repair night")).toBeNull();
    fireEvent.click(screen.getByRole("link", { name: "Past" }));
    expect(await screen.findByText("Community repair night")).toBeVisible();
    expect(screen.queryByText("Future fair")).toBeNull();
  });
  it("says so when a date tab has no events", async () => {
    renderPanel();
    await screen.findByText("Repair Collective");
    fireEvent.click(screen.getByRole("link", { name: "Upcoming" }));
    expect(await screen.findByText("No upcoming organized events.")).toBeVisible();
  });
  it("shows counts-only attendance across venues on its own tab", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/organized-events/attendance/") return {
        results: [
          { event_id: 73, title: "Community repair night", venue_name: "North Makerspace", starts_at: event.starts_at, status: "published", registered: 8, attended: 6, attendance_rate_percent: 75 },
          { event_id: 74, title: "Quiet fair", venue_name: "Partner Lab", starts_at: event.starts_at, status: "published", registered: 0, attended: 0, attendance_rate_percent: null },
        ],
        totals: { events: 2, registered: 8, attended: 6 }, truncated: false,
      };
      return response();
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/?organizedView=attendance"]}><OrganizedEventsPanel /></MemoryRouter></QueryClientProvider>);
    const table = await screen.findByRole("table", { name: "Attendance by event" });
    expect(table).toHaveTextContent("North Makerspace");
    expect(table).toHaveTextContent("Partner Lab");
    expect(table).toHaveTextContent("75%");
    expect(table).toHaveTextContent("—");
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/organized-events/?page=1&page_size=200");
  });

  it("does not read attendance until its tab is opened", async () => {
    renderPanel();
    await screen.findByText("Repair Collective");
    expect(staffRequest.mock.calls.some(([path]) => path === "/admin/organized-events/attendance/")).toBe(false);
  });

  it("drives previous and next controls from server links", async () => {
    renderPanel(response({ count: 100, next: "https://api.test/?page=2", previous: null }));
    const previous = await screen.findByRole("button", { name: "Previous" });
    const next = screen.getByRole("button", { name: "Next" });

    expect(previous).toBeDisabled();
    expect(next).toBeEnabled();
    staffRequest.mockResolvedValueOnce(response({
      count: 100, next: null, previous: "https://api.test/?page=1",
    }));
    fireEvent.click(next);

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/organized-events/?page=2&page_size=50",
    ));
    // Re-query rather than reusing the nodes captured above: the page-2 query key has no
    // cached data, so the whole pagination block unmounts while it loads and the old nodes
    // detach still carrying disabled="". No panel in this repo uses placeholderData, so the
    // unmount is the established behaviour rather than something to work around here.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();
      expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    });
  });

  it("opens the row on its event and host makerspace, then refreshes organized data", async () => {
    const { queryClient } = renderPanel();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    fireEvent.click(await screen.findByRole("button", { name: new RegExp(event.title) }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(`/admin/events/${event.id}/`));
    expect(screen.queryByLabelText("Title")).toBeNull();
    // Settings now lives under the drawer's More tab.
    fireEvent.click(await screen.findByRole("link", { name: "More" }));
    fireEvent.click(await screen.findByRole("link", { name: "Settings" }));
    fireEvent.change(await screen.findByLabelText("Title", { selector: "input" }), {
      target: { value: "Updated repair night" },
    });
    fireEvent.click(screen.getByRole("link", { name: "Overview" }));
    expect(screen.queryByLabelText("Title")).toBeNull();
    fireEvent.click(screen.getByRole("link", { name: "More" }));
    fireEvent.click(screen.getByRole("link", { name: "Settings" }));
    expect(screen.getByLabelText("Title", { selector: "input" })).toHaveValue("Updated repair night");
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({
      queryKey: ["events", event.makerspace_id, "list"],
    }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["events", "organized"] });
    await waitFor(() => expect(staffRequest.mock.calls.filter(
      ([path]) => path === "/admin/organized-events/?page=1&page_size=50",
    )).toHaveLength(2));
  });
});

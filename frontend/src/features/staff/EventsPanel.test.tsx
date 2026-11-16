import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { EventsPanel } from "./EventsPanel";
import { staffRequest } from "../../lib/api";
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()),
  staffRequest: vi.fn().mockResolvedValue({ count: 0, results: [], next: null, previous: null }) }));
const row = { id: 12, title: "Repair night", status: "draft", starts_at: "2099-10-16T12:00:00Z", ends_at: "2099-10-16T14:00:00Z", location: "Workshop", capacity: 20, registration_counts: { registered: 0, attended: 0, pending_approval: 0 } };
const none = vi.hoisted(() => ({ value: false }));
vi.mock("./eventsApi", () => ({
  useEvents: () => ({ data: none.value ? { count: 0, previous: null, next: null, results: [] } : { count: 1, previous: null, next: null, results: [row] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEvent: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./eventSeriesApi", () => ({
  useEventSeriesList: () => ({ data: { count: 0, results: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEventSeries: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./EventDrawer", () => ({ EventDrawer: ({ eventId, onClose }: { eventId: number; onClose: () => void }) => <><h1>Event {eventId}</h1><button onClick={onClose}>All events</button></> }));
vi.mock("./EventSeriesDrawer", () => ({ EventSeriesDrawer: () => null }));
vi.mock("./EventCollaborationReview", () => ({ useEventCollaborationReview: () => ({}) }));
vi.mock("./ListViewControls", () => ({ ListViewControls: () => null }));
function Location() { return <output>{useLocation().search}</output>; }
function show(url = "/admin/events") { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={[url]}><EventsPanel makerspaceId={3} /><Location /></MemoryRouter></QueryClientProvider>); }
describe("event layout composition", () => {
  it("opens the creation page from its header and returns to the list", async () => {
    show();
    expect(screen.queryByLabelText("Title")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "New event" }));
    expect(screen.getByRole("heading", { name: "New event", level: 1 })).toBeVisible();
    expect(screen.getByLabelText("Title")).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    // Essentials are on show; everything else waits behind a collapsed "More options".
    for (const label of ["Starts", "Ends", "Location", /^Capacity/, /^Registration audience/]) expect(screen.getByLabelText(label)).toBeVisible();
    expect(screen.getByLabelText("Anyone with the link can open this event")).toBeVisible();
    for (const label of ["Description", /^Registration price/, "Registration cutoff", /^Event time zone/, "Organizer approves each registration"]) expect(screen.getByLabelText(label)).not.toBeVisible();
    expect(screen.getByRole("heading", { name: "Organizers & partners", hidden: true })).not.toBeVisible();
    fireEvent.click(screen.getByText("More options"));
    expect(screen.getByLabelText("Description")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Organizers & partners" })).toBeVisible();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/organizations/?page=1&search=&active=true"));
    fireEvent.click(screen.getByRole("button", { name: "All events" }));
    expect(screen.getByRole("heading", { name: "Events", level: 1 })).toBeVisible();
  });
  it("keeps existing event deep links and preserves other URL filters when closing", () => {
    show("/admin/events?event=12&q=laser&eventTab=settings");
    expect(screen.getByRole("heading", { name: "Event 12" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "All events" }));
    expect(screen.getByRole("heading", { name: "Events" })).toBeVisible();
    expect(screen.getByText("?q=laser&eventTab=settings")).toBeVisible();
  });
  it("keeps series creation on its own full form", () => {
    show();
    fireEvent.click(screen.getByRole("button", { name: "New series" }));
    expect(screen.getByRole("heading", { name: "New series", level: 1 })).toBeVisible();
    expect(screen.getByLabelText("Series title")).toBeVisible();
    expect(screen.getByLabelText("First local date")).toBeVisible();
    expect(screen.queryByText("More options")).toBeNull();
  });
  it("uses URL tabs to expose drafts without the always-open create form", () => {
    show();
    fireEvent.click(screen.getByRole("tab", { name: "Drafts" }));
    expect(screen.getByRole("button", { name: /Repair night/ })).toBeVisible();
    expect(screen.queryByLabelText("Title")).toBeNull();
    expect(screen.getByText(/status=draft/)).toBeVisible();
  });
  it("answers a search or status tab with no events as a filtered empty state, not a first-run prompt", () => {
    none.value = true;
    try {
      show("/admin/events?q=zzz");
      expect(screen.getByText("No events match this search. Try another title.")).toBeVisible();
      expect(screen.queryByText(/Create your first event/)).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
      expect(screen.getByText("Your events will appear here. Create your first event.")).toBeVisible();
    } finally { none.value = false; }
  });
  it("names the empty status tab", () => {
    none.value = true;
    try {
      show("/admin/events?status=cancelled");
      expect(screen.getByText("No cancelled events.")).toBeVisible();
    } finally { none.value = false; }
  });
});

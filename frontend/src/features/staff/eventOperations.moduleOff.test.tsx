import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { EventsPanel } from "./EventsPanel";
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()),
  staffRequest: vi.fn().mockResolvedValue({ window_days: 180, k: 10, top_events: [], returning: { suppressed: true, attendees: null, returning_percent: null } }) }));
vi.mock("./eventsApi", () => ({
  useEvents: () => ({ data: { count: 0, previous: null, next: null, results: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEvent: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./eventSeriesApi", () => ({
  useEventSeriesList: () => ({ data: { count: 0, results: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEventSeries: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./EventDrawer", () => ({ EventDrawer: () => null }));
vi.mock("./EventSeriesDrawer", () => ({ EventSeriesDrawer: () => null }));
vi.mock("./EventCollaborationReview", () => ({ useEventCollaborationReview: () => ({}) }));
vi.mock("./ListViewControls", () => ({ ListViewControls: () => null }));
const show = (features: string[], url = "/admin/events") => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={[url]}><EventsPanel makerspaceId={3} enabledFeatures={features} /></MemoryRouter></QueryClientProvider>);

describe("event operations switches (decision 218: off = removed)", () => {
  it("shows the Insights tab and card only while events.space_insights is on", async () => {
    show(["events.space_insights"], "/admin/events?eventsView=insights");
    expect(screen.getByRole("tab", { name: "Insights" })).toBeInTheDocument();
    expect(await screen.findByText(/Best attended in the last 180 days/)).toBeInTheDocument();
  });
  it("removes the tab and ignores an insights link while off", () => {
    show([], "/admin/events?eventsView=insights");
    expect(screen.queryByRole("tab", { name: "Insights" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Best attended/)).not.toBeInTheDocument();
  });
});

import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { EventsPanel } from "./EventsPanel";
import { emptyRoomChoice, type RoomChoice } from "./EventRoomStep";

const mocks = vi.hoisted(() => ({ create: vi.fn(), withRoom: vi.fn(), toast: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<typeof import("../../lib/api")>()),
  staffRequest: vi.fn().mockResolvedValue({ count: 0, results: [], next: null, previous: null }) }));
vi.mock("./eventsApi", () => ({
  useEvents: () => ({ data: { count: 0, previous: null, next: null, results: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEvent: () => ({ mutate: mocks.create, isPending: false }),
}));
vi.mock("./eventVenueApi", async original => ({ ...(await original<typeof import("./eventVenueApi")>()),
  useCreateEventWithRoom: () => ({ mutate: mocks.withRoom, isPending: false, error: null }) }));
vi.mock("../../components/ui/toastStore", () => ({ toast: mocks.toast }));
vi.mock("./EventRoomStep", async original => ({ ...(await original<typeof import("./EventRoomStep")>()),
  EventRoomStep: ({ onChange }: { onChange: (next: RoomChoice) => void }) =>
    <button type="button" onClick={() => onChange({ ...emptyRoomChoice, mode: "house", space_id: 6 })}>Pick hall</button> }));
vi.mock("./eventSeriesApi", () => ({
  useEventSeriesList: () => ({ data: { count: 0, results: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useCreateEventSeries: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./EventDrawer", () => ({ EventDrawer: ({ eventId }: { eventId: number }) => <h1>Event {eventId}</h1> }));
vi.mock("./EventSeriesDrawer", () => ({ EventSeriesDrawer: () => null }));
vi.mock("./EventCollaborationReview", () => ({ useEventCollaborationReview: () => ({}) }));
vi.mock("./ListViewControls", () => ({ ListViewControls: () => null }));

it("creates the draft and its room in one call and reports a failed room step", () => {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/admin/events"]}>
    <EventsPanel makerspaceId={3} enabledModules={["events", "bookings"]} /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getAllByRole("button", { name: "New event" })[0]);
  fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Robot night" } });
  fireEvent.change(screen.getByLabelText("Starts"), { target: { value: "2030-01-01T10:00" } });
  fireEvent.change(screen.getByLabelText("Ends"), { target: { value: "2030-01-01T12:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Pick hall" }));
  fireEvent.click(screen.getByRole("button", { name: "Create event" }));
  expect(mocks.create).not.toHaveBeenCalled();
  expect(mocks.withRoom).toHaveBeenCalledWith({ event: expect.objectContaining({ title: "Robot night" }), room: { mode: "house", space_id: 6 } }, expect.anything());
  const { onSuccess } = mocks.withRoom.mock.calls[0][1] as { onSuccess: (result: unknown) => void };
  act(() => onSuccess({ event: { id: 44 }, room: { mode: "house", status: "failed", booking_id: null, booking_status: null, code: "room_unavailable" } }));
  expect(mocks.toast).toHaveBeenCalledWith(expect.stringContaining("The room is already booked at this time."), { tone: "error" });
  expect(screen.getByRole("heading", { name: "Event 44" })).toBeInTheDocument();
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GrantedEventsPanel } from "./GrantedEventsPanel";

const { accessible } = vi.hoisted(() => ({ accessible: vi.fn() }));
vi.mock("./eventStaffGrantsApi", () => ({ useAccessibleEvents: accessible }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: undefined }) }));
vi.mock("./EventRegistrationQueue", () => ({
  EventRegistrationQueue: ({ makerspaceId, onOpenEvent }: { makerspaceId: number; onOpenEvent: (id: number) => void }) =>
    <button type="button" onClick={() => onOpenEvent(44)}>Queue for space {makerspaceId}</button>,
}));
vi.mock("./EventDrawer", () => ({ EventDrawer: ({ eventId }: { eventId: number }) => <p>Opened assigned event {eventId}</p> }));

const grant = (permissions: string[]) => ({ event_id: 3, series_id: null, makerspace_id: 8, makerspace_slug: "maker", title: "Workshop",
  source: "event_grant" as const, permissions });

describe("registration queue for grant holders (A22)", () => {
  it("offers the queue to a grant holder who manages registrations and opens an event from it", () => {
    accessible.mockReturnValue({ data: { results: [] } });
    render(<GrantedEventsPanel grants={[grant(["manage_registrations"])]} />);
    fireEvent.click(screen.getByRole("button", { name: /more|actions|options/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Registrations waiting" }));
    fireEvent.click(screen.getByRole("button", { name: "Queue for space 8" }));
    expect(screen.getByText("Opened assigned event 44")).toBeInTheDocument();
  });

  it("is not offered without manage_registrations", () => {
    accessible.mockReturnValue({ data: { results: [] } });
    render(<GrantedEventsPanel grants={[grant(["check_in"])]} />);
    expect(screen.queryByText("Registrations waiting")).toBeNull();
  });
});

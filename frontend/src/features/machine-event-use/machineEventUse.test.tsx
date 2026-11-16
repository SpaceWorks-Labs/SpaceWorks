import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { EventMachineUsePanel } from "./EventMachineUsePanel";
import { EventLinkToggle } from "./EventLinkToggle";
import { EventPurposePicker } from "./EventPurposePicker";
import { StaffEventLink } from "./StaffEventLink";
import type { MachineEventLink, MachineUse } from "./api";

const api = vi.hoisted(() => ({ fetchMyEvents: vi.fn(), fetchLink: vi.fn(), saveLink: vi.fn(), fetchEventUse: vi.fn(), decideCost: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));

const faire = { id: 7, title: "Maker faire", starts_at: "2026-12-01T10:00:00Z", ends_at: null };
const wrap = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

function Harness() {
  const [value, setValue] = useState("");
  return <><EventPurposePicker makerspaceId={1} value={value} onChange={setValue} /><output>{value}</output></>;
}

describe("This is for an event", () => {
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); });

  it("offers only the member's own events, optional by default, and reports the choice", async () => {
    api.fetchMyEvents.mockResolvedValue([faire]);
    const { container } = wrap(<Harness />);
    const select = await screen.findByLabelText("This is for an event");
    expect(select).toHaveValue("");
    fireEvent.change(select, { target: { value: "7" } });
    expect(screen.getByRole("status")).toHaveTextContent("7");
    await expectNoA11yViolations(container);
  });

  it("shows nothing when the member has no events to pick", async () => {
    api.fetchMyEvents.mockResolvedValue([]);
    const { container } = wrap(<Harness />);
    await waitFor(() => expect(api.fetchMyEvents).toHaveBeenCalled());
    expect(container.querySelector("select")).toBeNull();
  });
});

describe("Area manager's event link", () => {
  const link = (over: Partial<MachineEventLink> = {}): MachineEventLink => ({ event: null, source: "", locked: false, options: [faire], ...over });
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); });

  it("sets and clears the event", async () => {
    api.fetchLink.mockResolvedValue(link());
    api.saveLink.mockResolvedValue(link({ event: faire }));
    wrap(<StaffEventLink makerspaceId={1} kind="session" id={5} />);
    fireEvent.change(await screen.findByLabelText("Logged for event"), { target: { value: "7" } });
    await waitFor(() => expect(api.saveLink).toHaveBeenCalledWith(1, "session", 5, 7));
    fireEvent.change(await screen.findByLabelText("Logged for event"), { target: { value: "" } });
    await waitFor(() => expect(api.saveLink).toHaveBeenLastCalledWith(1, "session", 5, null));
  });

  it("locks the control once the organiser approved the cost", async () => {
    api.fetchLink.mockResolvedValue(link({ event: faire, locked: true }));
    wrap(<StaffEventLink makerspaceId={1} kind="request" id={9} />);
    expect(await screen.findByLabelText("Logged for event")).toBeDisabled();
  });
});

describe("Event machine use section", () => {
  const use = (over: Partial<MachineUse> = {}): MachineUse => ({ can_decide_costs: true, rows: [{
    link_id: 3, kind: "request", subject_id: 9, title: "Faire signage", machine_type: "Laser", person: "Asha", minutes: 40,
    consumables: [{ label: "Acrylic", unit: "count", quantity: "2" }], source: "requester", created_at: "2026-11-01T10:00:00Z",
    charge: { amount: "50.00", currency: "INR", status: "pending" }, cost_decision: null }],
  totals: { sessions: 0, requests: 1, minutes: 40, consumables: [{ label: "Acrylic", unit: "count", quantity: "2" }],
    charged: { INR: "50.00" }, approved_to_event: {} }, ...over });
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); });

  it("lists the use and lets an organiser approve the cost (a record, no payment)", async () => {
    api.fetchEventUse.mockResolvedValue(use());
    api.decideCost.mockResolvedValue(undefined);
    const { container } = wrap(<EventMachineUsePanel makerspaceId={1} eventId={7} />);
    expect(await screen.findByText("Faire signage")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Approve charging the event" }));
    await waitFor(() => expect(api.decideCost).toHaveBeenCalledWith(1, 7, 3, "approved"));
    await expectNoA11yViolations(container);
  });

  it("hides the decision button from someone who cannot decide", async () => {
    api.fetchEventUse.mockResolvedValue(use({ can_decide_costs: false }));
    wrap(<EventMachineUsePanel makerspaceId={1} eventId={7} />);
    await screen.findByText("Faire signage");
    expect(screen.queryByRole("button", { name: /charging the event/ })).toBeNull();
  });
});

describe("Event link on a booking", () => {
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); });

  it("offers the area manager's editor on demand and explains a booking that cannot carry an event", async () => {
    api.fetchLink.mockRejectedValue(new Error("not a machine booking"));
    wrap(<EventLinkToggle makerspaceId={1} kind="booking" id={11} statusUnknown />);
    expect(api.fetchLink).not.toHaveBeenCalled(); // lazy: a list of bookings fetches nothing until opened
    fireEvent.click(screen.getByRole("button", { name: "Event" }));
    expect(await screen.findByText(/Only machine-time bookings, sessions and jobs/)).toBeVisible();
    expect(api.fetchLink).toHaveBeenCalledWith(1, "booking", 11);
  });

  it("sets a booking's event through the same route", async () => {
    api.fetchLink.mockResolvedValue({ event: null, source: "", locked: false, options: [faire] });
    api.saveLink.mockResolvedValue({ event: faire, source: "manager", locked: false, options: [faire] });
    wrap(<EventLinkToggle makerspaceId={1} kind="booking" id={11} statusUnknown />);
    fireEvent.click(screen.getByRole("button", { name: "Event" }));
    fireEvent.change(await screen.findByLabelText("Logged for event"), { target: { value: "7" } });
    await waitFor(() => expect(api.saveLink).toHaveBeenCalledWith(1, "booking", 11, 7));
  });
});

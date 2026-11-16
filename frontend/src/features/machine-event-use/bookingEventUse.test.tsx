import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BookingEventPicker } from "./BookingEventPicker";
import { EventLinkToggle } from "./EventLinkToggle";
import { StaffBookingEventPicker } from "./StaffBookingEventPicker";

const api = vi.hoisted(() => ({ fetchMyEvents: vi.fn(), fetchStaffEventOptions: vi.fn(), fetchLink: vi.fn(), saveLink: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));
const tenant = vi.hoisted(() => ({ mode: "central" as "central" | "single" }));
vi.mock("../../lib/tenant", async original => ({ ...(await original<object>()),
  useOptionalTenant: () => tenant.mode === "single" ? { mode: "single", bootstrap: { makerspace: { id: 4 } } } : { mode: "central" } }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: { makerspace: { id: 9 } } }) }));

const faire = { id: 7, title: "Maker faire", starts_at: "2026-12-01T10:00:00Z", ends_at: null };
const wrap = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

function Booking({ slug = "lab" }: { slug?: string }) {
  const [value, setValue] = useState("");
  return <><BookingEventPicker makerspaceSlug={slug} value={value} onChange={setValue} /><output>{value}</output></>;
}

describe("Machine booking form: This is for an event", () => {
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); tenant.mode = "central"; });

  it("looks the member's events up in the space found from the slug and reports the choice", async () => {
    api.fetchMyEvents.mockResolvedValue([faire]);
    wrap(<Booking />);
    fireEvent.change(await screen.findByLabelText("This is for an event"), { target: { value: "7" } });
    expect(api.fetchMyEvents).toHaveBeenCalledWith(9);
    expect(screen.getByRole("status")).toHaveTextContent("7");
  });

  it("uses the single-space bootstrap id on a space's own domain", async () => {
    tenant.mode = "single";
    api.fetchMyEvents.mockResolvedValue([faire]);
    wrap(<Booking />);
    await screen.findByLabelText("This is for an event");
    expect(api.fetchMyEvents).toHaveBeenCalledWith(4);
  });

  it("shows nothing when the member has no events", async () => {
    api.fetchMyEvents.mockResolvedValue([]);
    const { container } = wrap(<Booking />);
    await waitFor(() => expect(api.fetchMyEvents).toHaveBeenCalled());
    expect(container.querySelector("select")).toBeNull();
  });
});

describe("Staff booking form picker", () => {
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); });

  it("lists the space's open events and reports the choice", async () => {
    api.fetchStaffEventOptions.mockResolvedValue([faire]);
    const onChange = vi.fn();
    wrap(<StaffBookingEventPicker makerspaceId={1} value="" onChange={onChange} />);
    fireEvent.change(await screen.findByLabelText("This is for an event"), { target: { value: "7" } });
    expect(onChange).toHaveBeenCalledWith("7");
    expect(api.fetchStaffEventOptions).toHaveBeenCalledWith(1);
  });

  it("is hidden when staff may not see the list", async () => {
    api.fetchStaffEventOptions.mockRejectedValue(new Error("404"));
    const { container } = wrap(<StaffBookingEventPicker makerspaceId={1} value="" onChange={() => undefined} />);
    await waitFor(() => expect(api.fetchStaffEventOptions).toHaveBeenCalled());
    expect(container.querySelector("select")).toBeNull();
  });
});

describe("Booking card toggle", () => {
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); });

  it("shows the event the list already carries, without fetching anything until opened", () => {
    wrap(<EventLinkToggle makerspaceId={1} kind="booking" id={11} eventTitle="Maker faire" />);
    expect(screen.getByText(/For event: Maker faire/)).toBeVisible();
    expect(api.fetchLink).not.toHaveBeenCalled();
  });

  it("says nothing is logged when the booking has no event, and opens and closes the editor", async () => {
    api.fetchLink.mockResolvedValue({ event: null, source: "", locked: false, options: [faire] });
    wrap(<EventLinkToggle makerspaceId={1} kind="booking" id={11} eventTitle={null} />);
    expect(screen.getByText("Not logged for an event")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Event" }));
    expect(await screen.findByLabelText("Logged for event")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByLabelText("Logged for event")).toBeNull();
  });
});

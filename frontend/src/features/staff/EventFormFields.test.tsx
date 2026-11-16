import { useState } from "react";
import { fireEvent, render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { describe, expect, it, vi } from "vitest";

import {
  EventFields,
  emptyEventForm,
  payloadFor,
  type EventFormValues,
} from "./EventFormFields";
// The price-list note reads the staff session cache; these forms are tested without one.
vi.mock("./pricing/PricingNote", () => ({ EventPriceNote: () => null }));

function Harness({ approvalLocked = false }: { approvalLocked?: boolean }) {
  const [values, setValues] = useState<EventFormValues>({
    ...emptyEventForm,
    title: "Workshop",
    starts_at: "2026-09-03T10:00",
    ends_at: "2026-09-03T12:00",
  });
  return <EventFields values={values} setValues={setValues} approvalLocked={approvalLocked} />;
}

describe("EventFields registration policy", () => {
  it("keeps the two cutoff modes mutually exclusive", () => {
    render(<Harness />);
    const mode = screen.getByLabelText("Registration cutoff");

    fireEvent.change(mode, { target: { value: "lead" } });
    expect(screen.getByLabelText("Minutes before start")).toBeTruthy();
    expect(screen.queryByLabelText("Cutoff time")).toBeNull();

    fireEvent.change(mode, { target: { value: "absolute" } });
    expect(screen.getByLabelText("Cutoff time")).toBeTruthy();
    expect(screen.queryByLabelText("Minutes before start")).toBeNull();
  });

  it("locks approval after draft and serializes only the selected cutoff", () => {
    render(<Harness approvalLocked />);
    expect(screen.getByLabelText("Organizer approves each registration")).toBeDisabled();

    const payload = payloadFor({
      ...emptyEventForm,
      title: "Workshop",
      starts_at: "2026-09-03T10:00",
      ends_at: "2026-09-03T12:00",
      registration_cutoff_lead_minutes: 30,
    });
    expect(payload.registration_cutoff_at).toBeNull();
    expect(payload.registration_cutoff_lead_minutes).toBe(30);
  });

  it("edits member cancellation hours and restores the start-time default", () => {
    render(<Harness />);
    const hours = screen.getByLabelText(/Member cancellation closes hours before/);
    fireEvent.change(hours, { target: { value: "24" } });
    expect(hours).toHaveValue(24);
    fireEvent.change(hours, { target: { value: "" } });
    expect(hours).toHaveValue(null);
    const payload = payloadFor({
      ...emptyEventForm, starts_at: "2026-09-03T10:00", ends_at: "2026-09-03T12:00",
      cancellation_cutoff_hours: 24,
    });
    expect(payload.cancellation_cutoff_hours).toBe(24);
  });
  it("keeps comma-separated tag entry editable and trims tags at submission", () => {
    render(<Harness />);
    const tags = screen.getByLabelText("Tags (comma separated)");
    fireEvent.change(tags, { target: { value: "wood," } });
    expect(tags).toHaveValue("wood,");
    const payload = payloadFor({ ...emptyEventForm, starts_at: "2026-09-03T10:00", ends_at: "2026-09-03T12:00", registration_audience: "accounts", tags: [" wood ", "", "metal"] });
    expect(payload.tags).toEqual(["wood", "metal"]);
    expect(payload.registration_audience).toBe("accounts");
  });

});

import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { EventCreatePreview } from "./EventCreatePreview";
import { emptyEventForm } from "./EventFormFields";
import { EventAtAGlance } from "./EventOverview";
import type { StaffEvent } from "./eventsApiTypes";

// No cached staff makerspace list: useStaffChargesOn fails open, so the price line shows.
const wrap = (ui: ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
const event = { id: 3, status: "draft", starts_at: "2026-12-01T10:00:00Z", ends_at: "2026-12-01T12:00:00Z", timezone_name: "UTC",
  location: "Lab", is_public: true, registration_open: true, effective_registration_cutoff_at: null, registration_audience: "members",
  offline_checkin_enabled: false, payment_amount: "12.50", currency: "eur", registration_counts: {} } as unknown as StaffEvent;

describe("event price currency", () => {
  it("shows the event price in the event's currency at a glance", () => {
    wrap(<EventAtAGlance event={event} />);
    expect(screen.getByText("€12.50")).toBeInTheDocument();
  });

  it("calls a zero price free", () => {
    wrap(<EventAtAGlance event={{ ...event, payment_amount: "0.00" }} />);
    expect(screen.getByText("Free")).toBeInTheDocument();
  });

  it("previews capacity and the price in the space's currency", () => {
    wrap(<EventCreatePreview values={{ ...emptyEventForm, capacity: 30, payment_amount: "5.00" }} currency="usd" />);
    expect(screen.getByText("30 places · $5.00")).toBeInTheDocument();
  });

  it("previews unlimited places and a bare amount when the currency is unknown", () => {
    wrap(<EventCreatePreview values={{ ...emptyEventForm, capacity: 0, payment_amount: "5.00" }} />);
    expect(screen.getByText("Unlimited places · 5.00")).toBeInTheDocument();
  });
});

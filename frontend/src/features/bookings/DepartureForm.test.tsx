import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

const { memberRequest, staffRequest } = vi.hoisted(() => ({ memberRequest: vi.fn(), staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), memberRequest, staffRequest }));

import { DepartureForm, DepartureSummary } from "./DepartureForm";
import { BookingCheckout } from "../staff/BookingCheckout";
import type { Booking } from "../staff/bookingsApi";

describe("DepartureForm", () => {
  it("submits all good without a remark", () => {
    const onSubmit = vi.fn();
    render(<DepartureForm audience="member" onSubmit={onSubmit} submitLabel="Check out" />);
    expect(screen.getByRole("radio", { name: "All good" })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Check out" }));
    expect(onSubmit).toHaveBeenCalledWith({ outcome: "all_good", remark: "" });
  });

  it("requires a remark for anything that went wrong", () => {
    const onSubmit = vi.fn();
    render(<DepartureForm audience="staff" onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole("radio", { name: "Something was damaged" }));
    expect(screen.getByText("Remark (required)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record check-out" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/Describe what was wrong/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Remark/), { target: { value: "  Drill bit snapped " } });
    fireEvent.click(screen.getByRole("button", { name: "Record check-out" }));
    expect(onSubmit).toHaveBeenCalledWith({ outcome: "damaged", remark: "Drill bit snapped" });
  });

  it("summarises a recorded departure", () => {
    render(<DepartureSummary departure={{ outcome: "left_early", remark: "Feeling unwell", source: "member",
      recorded_at: "2026-11-01T10:30:00Z", recorded_by: "ada" }} />);
    expect(screen.getByText("Left early")).toBeInTheDocument();
    expect(screen.getByText(/reported by the booker/)).toBeInTheDocument();
    expect(screen.getByText("“Feeling unwell”")).toBeInTheDocument();
  });
});

describe("staff check-out on a request card", () => {
  const started: Booking = { id: 9, public_token: "t", space_id: 4, name: "Ada", email: "a@example.test", phone: "1",
    starts_at: new Date(Date.now() - 600_000).toISOString(), ends_at: new Date(Date.now() + 3_000_000).toISOString(),
    status: "confirmed", note: "", custom_answers: null, payment: null, created_at: "2026-10-01T00:00:00Z",
    decision_reason: "", departures: [], departed_at: null };

  it("records a check-out through the arrival depart endpoint", async () => {
    staffRequest.mockResolvedValue({ departed_at: "2026-11-01T11:00:00Z", can_depart: false });
    const client = new QueryClient();
    render(<QueryClientProvider client={client}><BookingCheckout makerspaceId={7} spaceId={4} booking={started} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Record check-out" }));
    fireEvent.click(screen.getByRole("radio", { name: "Something was wrong" }));
    fireEvent.change(screen.getByLabelText(/Remark/), { target: { value: "Door left open" } });
    fireEvent.click(screen.getByRole("button", { name: "Record check-out" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/spaces/4/arrival/9/depart/",
      expect.objectContaining({ body: JSON.stringify({ outcome: "issue", remark: "Door left open" }) })));
  });

  it("shows the decision reason and hides check-out for a future booking", () => {
    const future = { ...started, status: "cancelled" as const, decision_reason: "Space closed",
      starts_at: new Date(Date.now() + 86_400_000).toISOString() };
    render(<BookingCheckout makerspaceId={7} spaceId={4} booking={future} />);
    expect(screen.getByText("Space closed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Record check-out" })).not.toBeInTheDocument();
  });
});

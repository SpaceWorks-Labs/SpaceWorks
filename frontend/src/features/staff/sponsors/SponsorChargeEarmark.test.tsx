import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { chargeBody, SponsorCharges } from "./SponsorMoneyAndEvents";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest }));

const charge = { id: 5, sponsor: 3, amount: "50000.00", currency: "inr", description: "Prize money", payment_id: 8,
  payment_status: "pending", created_at: "2026-11-05T00:00:00Z", event: 41, earmark: "prize_pool" };

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockImplementation((path: string, init?: RequestInit) =>
  Promise.resolve(path.includes("/events") ? { count: 1, next: null, previous: null, results: [{ id: 41, title: "HackDay" }] }
    : init?.method === "POST" ? charge : [charge])); });

describe("sponsorship earmark (G8)", () => {
  it("only earmarks to a prize pool when an event is chosen", () => {
    expect(chargeBody("10", "x", "", true)).toEqual({ amount: "10", description: "x", event_id: null, earmark: "general" });
    expect(chargeBody("10", "x", "41", true)).toEqual({ amount: "10", description: "x", event_id: 41, earmark: "prize_pool" });
  });

  it("shows the event and earmark and sends them when recording", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SponsorCharges makerspaceId={2} sponsorId={3} canRecord /></QueryClientProvider>);
    expect(await screen.findByText(/HackDay · prize pool/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "100" } });
    fireEvent.change(screen.getByLabelText("Event (optional)"), { target: { value: "41" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /prize pool/ }));
    fireEvent.click(screen.getByRole("button", { name: "Record as owed" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/sponsors/3/charges",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ amount: "100", description: "", event_id: 41, earmark: "prize_pool" }) })));
  });
});

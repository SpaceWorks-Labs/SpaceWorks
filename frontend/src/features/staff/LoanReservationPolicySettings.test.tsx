import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { LoanReservationPolicySettings, type ReservationPolicy } from "./LoanReservationPolicySettings";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: request }));

const policy: ReservationPolicy = { pickup_window_hours: 48, reservation_max_days_ahead: 14, waitlist_offer_hours: 24 };

beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "PUT" ? JSON.parse(String(init.body)) : policy);
});

it("loads and saves pickup and waitlist timing with PUT", async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <LoanReservationPolicySettings makerspaceId={7} /></QueryClientProvider>);
  const pickup = await screen.findByLabelText(/Hours to collect an accepted request/);
  expect(pickup).toHaveValue(48);
  expect(screen.getByText("0 = accepted requests never expire.")).toBeInTheDocument();
  fireEvent.change(pickup, { target: { value: "0" } });
  fireEvent.change(screen.getByLabelText(/Hours a waitlist offer is held/), { target: { value: "12" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/loan-reservation-policy", {
    method: "PUT", body: JSON.stringify({ ...policy, pickup_window_hours: 0, waitlist_offer_hours: 12 }),
  }));
  expect(await screen.findByRole("status")).toHaveTextContent("Pickup and waitlist timing saved.");
});

it("shows a settings-authority refusal", async () => {
  request.mockImplementation(async (_path: string, init?: RequestInit) => {
    if (init?.method === "PUT") throw new Error("This setting is locked by the Space Manager.");
    return policy;
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <LoanReservationPolicySettings makerspaceId={7} /></QueryClientProvider>);
  fireEvent.change(await screen.findByLabelText(/How far ahead/), { target: { value: "30" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("locked by the Space Manager");
});

import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { MemberEventEquipment } from "./MemberEventEquipment";

const api = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", () => api);

function view() {
  return render(<MemoryRouter><QueryClientProvider client={new QueryClient()}>
    <MemberEventEquipment makerspaceId={7} registrationId={21} requestHref="/inventory" historyHref="/member/loans/history" />
  </QueryClientProvider></MemoryRouter>);
}

beforeEach(() => { vi.resetAllMocks(); });

it("lists the registrant's own event equipment with status and due-back", async () => {
  api.memberRequest.mockResolvedValue({ event_id: 4, event_ends_at: null, can_request: true, requests: [{
    public_token: "tok", status: "issued", created_at: "2026-01-01T00:00:00Z", return_due_at: "2026-01-02T00:00:00Z", overdue: true,
    items: [{ product_name: "Multimeter", requested_quantity: 2, accepted_quantity: 2, issued_quantity: 1, returned_quantity: 0 }],
  }] });
  view();
  expect(await screen.findByRole("heading", { name: "Your equipment for this event" })).toBeTruthy();
  expect(api.memberRequest.mock.calls[0][0]).toBe("/member/makerspaces/7/event-registrations/21/equipment/");
  expect(screen.getByText("Multimeter × 1")).toBeTruthy();
  expect(screen.getByText("Overdue")).toBeTruthy();
  expect(screen.getByText(/Return by/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "Request equipment" }).getAttribute("href")).toBe("/inventory");
});

it("offers a request when the event lends but nothing is planned yet", async () => {
  api.memberRequest.mockResolvedValue({ event_id: 4, event_ends_at: null, can_request: true, requests: [] });
  view();
  expect(await screen.findByRole("link", { name: "Request equipment" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Your borrowing history" })).toBeNull();
});

it.each([
  ["refused", () => api.memberRequest.mockRejectedValue(Object.assign(new Error("Not found"), { status: 404 }))],
  ["empty and closed", () => api.memberRequest.mockResolvedValue({ event_id: 4, event_ends_at: null, can_request: false, requests: [] })],
])("renders nothing when %s", async (_label, arrange) => {
  arrange();
  const { container } = view();
  await vi.waitFor(() => expect(api.memberRequest).toHaveBeenCalled());
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(container.textContent).toBe("");
});

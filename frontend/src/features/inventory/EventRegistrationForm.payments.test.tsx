import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EventRegistrationForm } from "./EventRegistrationForm";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), tenantPublicRequest: request, tenantMemberRequest: request }));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
vi.mock("../../lib/tenant", async (importOriginal) => ({ ...await importOriginal<typeof import("../../lib/tenant")>(),
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } }) }));

function view(paymentsHref: string) {
  return <QueryClientProvider client={new QueryClient()}><MemoryRouter><EventRegistrationForm
    makerspaceSlug="venue" publicToken="event" waitlist={false} approvalRequired={false}
    customForm={null} paymentsHref={paymentsHref} /></MemoryRouter></QueryClientProvider>;
}

describe("paid event registration confirmation", () => {
  beforeEach(() => { request.mockReset(); request.mockResolvedValue({ status: "registered" }); });

  it("points a registered member at their Payments for the fee", async () => {
    render(view("/m/venue/member/payments"));
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(await screen.findByRole("link", { name: "Payments" })).toHaveAttribute("href", "/m/venue/member/payments");
  });

  it("says nothing about payment for a free event", async () => {
    render(view(""));
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    await screen.findByText("Registration received");
    expect(screen.queryByRole("link", { name: "Payments" })).toBeNull();
  });
});

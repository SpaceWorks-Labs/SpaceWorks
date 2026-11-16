import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EventRegistrationForm } from "./EventRegistrationForm";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), tenantPublicRequest: request, tenantMemberRequest: request }));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
vi.mock("../../lib/tenant", () => ({ useTenantPath: () => (path: string) => `/m/venue/${path}`,
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } }) }));
// The live price preview posts its own quote; these tests script the registration requests in order.
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));

function view(version = "v1", client = new QueryClient()) {
  return <QueryClientProvider client={client}><MemoryRouter><EventRegistrationForm
    makerspaceSlug="venue" publicToken="event" waitlist={false} approvalRequired={false}
    audience="participating_organizations" customForm={null}
    hostWaiver={{ id: 3, version, body: `Host terms ${version}` }}
  /></MemoryRouter></QueryClientProvider>;
}

describe("organization event host consent", () => {
  beforeEach(() => { request.mockReset(); request.mockResolvedValue({ registration_id: 7, status: "registered" }); });
  it("requires explicit consent and submits the exact current waiver tuple", async () => {
    render(view());
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(request).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Accept the current host waiver");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    await waitFor(() => expect(request).toHaveBeenCalledOnce());
    const body = JSON.parse(request.mock.calls[0][2].body);
    expect(body).toMatchObject({ host_waiver_id: 3, host_waiver_version: "v1", host_waiver_accepted: true });
  });
  it("clears earlier consent when a live eligibility refresh changes the waiver", () => {
    const client = new QueryClient();
    const rendered = render(view("v1", client));
    fireEvent.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("checkbox")).toBeChecked();
    rendered.rerender(view("v2", client));
    expect(screen.getByText("Host terms v2")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });
});

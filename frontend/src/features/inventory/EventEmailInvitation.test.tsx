import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { EventRegistrationForm } from "./EventRegistrationForm";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), tenantPublicRequest: request, tenantMemberRequest: request }));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
vi.mock("../../lib/tenant", async (importOriginal) => ({ ...await importOriginal<typeof import("../../lib/tenant")>(),
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } }) }));
beforeEach(() => { request.mockReset(); });

it("submits an email-bound invitation without requiring a code", async () => {
  request.mockResolvedValue({ status: "registered" });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><EventRegistrationForm makerspaceSlug="lab" publicToken="event"
    audience="invite" waitlist={false} approvalRequired={false} customForm={[]} /></QueryClientProvider>);
  expect(screen.getByLabelText("Invitation code")).not.toBeRequired();
  fireEvent.click(screen.getByRole("button", { name: "Register" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("lab", "/public/lab/events/event/register/",
    expect.objectContaining({ body: JSON.stringify({ website: "", custom_answers: {} }) })));
  expect(await screen.findByRole("heading", { name: "Registration received" })).toBeInTheDocument();
});

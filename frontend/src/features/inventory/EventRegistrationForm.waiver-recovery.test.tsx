import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { OrganizationEventAdmission, organizationEligibilityKey } from "../events/OrganizationEventAdmission";
import type { PublicEventDetail } from "../events/eventTicketTypes";

const { eligibility, request } = vi.hoisted(() => ({ eligibility: vi.fn(), request: vi.fn() }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual("../../lib/api"),
  getAccessToken: () => "test-session",
  memberRequest: async () => ({ id: 17 }),
  tenantMemberRequest: (slug: string, path: string, options?: RequestInit) =>
    options?.method === "POST" ? request(slug, path, options) : eligibility(slug, path, options),
  tenantPublicRequest: request,
}));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
vi.mock("../../lib/tenant", () => ({ useTenantPath: () => (path: string) => `/m/venue/${path}`,
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } }) }));
// The live price preview posts its own quote; these tests script the registration requests in order.
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));

const oldWaiver = { id: 3, version: "v1", body: "Original host terms" };
const allowed = (host_waiver = oldWaiver) => ({ eligible: true, reason: null, host_waiver });
const event: PublicEventDetail = {
  title: "Workshop", description: "Workshop details", location: "Host venue",
  starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T12:00:00Z",
  capacity: 10, payment_amount: "0.00", currency: "USD",
  effective_registration_cutoff_at: null, image_url: null, status: "published", series: null,
  public_token: "event-one", registration_audience: "participating_organizations",
  registration_open: true, registration_requires_approval: false, availability: "Available",
  custom_form: [{ id: "reason", label: "Why attend?", type: "short_text", required: true, options: [] }],
};

describe("stale host waiver recovery", () => {
  beforeEach(() => { eligibility.mockReset(); request.mockReset(); });

  it.each([
    { id: 3, version: "v2", body: "Revised host terms" },
    { id: 4, version: "v1", body: "Replacement host terms" },
  ])("refetches waiver $id/$version and requires fresh consent before retry", async newWaiver => {
    eligibility.mockResolvedValueOnce(allowed()).mockResolvedValue(allowed(newWaiver));
    request.mockRejectedValueOnce(new StructuredApiError(403, {
      code: "host_waiver_required", detail: "Accept the current host waiver.",
    })).mockResolvedValue({ registration_id: 7, status: "registered" });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const unrelatedKeys = [
      organizationEligibilityKey("other-venue", "event-one", 17),
      organizationEligibilityKey("venue", "other-event", 17),
    ];
    unrelatedKeys.forEach(key => client.setQueryData(key, allowed()));
    const view = render(<MemoryRouter><QueryClientProvider client={client}>
      <OrganizationEventAdmission event={event} makerspaceSlug="venue" />
    </QueryClientProvider></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Check registration eligibility" }));
    fireEvent.click(await screen.findByRole("button", { name: "Register" }));
    const answer = screen.getByRole("textbox", { name: /Why attend/ });
    fireEvent.change(answer, { target: { value: "Build a telescope" } });
    fireEvent.click(screen.getByRole("checkbox"));
    const submit = screen.getAllByRole("button", { name: "Register" })[0];
    fireEvent.click(submit);

    await screen.findByText(newWaiver.body);
    await waitFor(() => expect(submit).toBeEnabled());
    expect(eligibility).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.getByRole("textbox", { name: /Why attend/ })).toBe(answer);
    expect(answer).toHaveValue("Build a telescope");
    const body = (index: number) => JSON.parse(request.mock.calls[index][2].body);
    expect(body(0)).toMatchObject({
      host_waiver_id: 3, host_waiver_version: "v1", host_waiver_accepted: true,
    });
    fireEvent.click(submit);
    expect(request).toHaveBeenCalledOnce();
    expect(screen.getAllByRole("alert").some(alert => alert.textContent === "Accept the current host waiver.")).toBe(true);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(submit);
    await screen.findByText("Registration received");
    expect(request).toHaveBeenCalledTimes(2);
    expect(body(1)).toMatchObject({
      host_waiver_id: newWaiver.id, host_waiver_version: newWaiver.version,
      host_waiver_accepted: true, custom_answers: { reason: "Build a telescope" },
    });
    unrelatedKeys.forEach(key => expect(client.getQueryState(key)?.isInvalidated).toBe(false));
    view.unmount(); client.clear();
  });
});

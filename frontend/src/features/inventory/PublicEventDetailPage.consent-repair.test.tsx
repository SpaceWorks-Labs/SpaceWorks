import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicEventDetailPage } from "./PublicEventDetailPage";
import { StructuredApiError } from "../../lib/api";
import type { EventEligibility } from "../events/OrganizationEventAdmission";
import { organizationEligibilityKey } from "../events/OrganizationEventAdmission";
import type { PublicEventDetail } from "../events/eventTicketTypes";

// The revamp's action card is a phone sheet below 768px; these tests drive the inline tablet/desktop card.
Object.defineProperty(window, "matchMedia", { configurable: true, value: (query: string) => ({ matches: true, media: query,
  addEventListener: () => undefined, removeEventListener: () => undefined }) });

const { eligibility, request } = vi.hoisted(() => ({ eligibility: vi.fn(), request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"),
  getAccessToken: () => "test-session", memberRequest: async () => ({ id: 17 }),
  tenantMemberRequest: (slug: string, path: string, options?: RequestInit) =>
    options?.method === "POST" ? request(slug, path, options) : eligibility(slug, path, options),
  tenantPublicRequest: request,
}));
vi.mock("../../lib/tenant", () => ({
  // The registration card waits for the space's features before choosing ordinary or programme entry.
  useTenant: () => ({ mode: "single", slug: "venue", bootstrap: { makerspace: { id: 1, name: "Venue" }, branding: {}, theme: {}, features: [], modules: [] } }),
  useTenantPath: () => (path: string) => `/m/venue/${path}`,
}));

const waiver = { id: 4, version: "v2", body: "Revised host terms" };
const repair: EventEligibility = { eligible: false, reason: "registration_closed",
  consent_repair_required: true, host_waiver: waiver };
const closed: EventEligibility = { ...repair, consent_repair_required: false, host_waiver: null };
const event: PublicEventDetail = {
  public_token: "event-one", title: "Workshop", description: "Details", location: "Venue",
  starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T12:00:00Z",
  capacity: 10, payment_amount: "12.00", currency: "USD", image_url: null,
  status: "published", series: null, effective_registration_cutoff_at: "2026-10-19T10:00:00Z",
  registration_audience: "participating_organizations", registration_open: false,
  registration_requires_approval: true, availability: "Full", ticket_selection_required: true,
  ticket_types: [], promo_codes_enabled: true,
  custom_form: [{ id: "reason", label: "Why attend?", type: "short_text", required: true, options: [] }],
};

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/events/event-one"]}>
    <Routes><Route path="/events/:publicToken" element={<PublicEventDetailPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
  return { client, view };
}

describe("owned registration consent after signup closes", () => {
  beforeEach(() => {
    eligibility.mockReset(); request.mockReset();
    request.mockImplementation((_slug, _path, options) => Promise.resolve(options?.method === "POST"
      ? { registration_id: 7, status: "pending_approval" } : event));
  });

  it.each(["pending_approval", "waitlisted", "registered"])("renews a %s registration from the closed detail page", async status => {
    let saved = false;
    eligibility.mockImplementation(async () => saved ? closed : repair);
    request.mockImplementation((_slug, _path, options) => {
      if (options?.method !== "POST") return Promise.resolve(event);
      saved = true;
      return Promise.resolve({ registration_id: 7, status });
    });
    const { client, view } = setup();
    const unrelated = organizationEligibilityKey("other", "event-one", 17);
    client.setQueryData(unrelated, repair);
    expect(await screen.findByText("Registration is closed.")).toBeVisible();
    expect(eligibility).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Review registration consent" }));
    await screen.findByRole("heading", { name: "Renew registration consent" });
    expect(screen.queryByRole("textbox", { name: /Why attend/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Ticket type")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Accept the current host waiver.");
    expect(request.mock.calls.some(call => call[2]?.method === "POST")).toBe(false);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    await screen.findByText("Your registration consent has been updated.");
    expect(request).toHaveBeenCalledWith("venue", "/public/venue/events/event-one/register/", {
      method: "POST", body: JSON.stringify({ host_waiver_id: 4, host_waiver_version: "v2", host_waiver_accepted: true }),
    });
    await waitFor(() => expect(eligibility).toHaveBeenCalledTimes(2));
    expect(client.getQueryState(unrelated)?.isInvalidated).toBe(false);
    view.unmount(); client.clear();
  });

  it.each(["no owned live registration", "consent already current"])("keeps signup closed with %s", async () => {
    eligibility.mockResolvedValue(closed);
    const { client, view } = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Review registration consent" }));
    await waitFor(() => expect(client.getQueryData(organizationEligibilityKey("venue", "event-one", 17))).toEqual(closed));
    expect(screen.getByText("Registration is closed.")).toBeVisible();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^(Apply|Register|Save consent)$/ })).not.toBeInTheDocument();
    view.unmount(); client.clear();
  });

  it("requires fresh acceptance if the waiver changes during renewal", async () => {
    const updated = { id: 5, version: "v3", body: "Newest host terms" };
    eligibility.mockResolvedValueOnce(repair).mockResolvedValue({ ...repair, host_waiver: updated });
    let attempts = 0;
    request.mockImplementation((_slug, _path, options) => {
      if (options?.method !== "POST") return Promise.resolve(event);
      if (++attempts === 1) return Promise.reject(new StructuredApiError(400, {
        code: "host_waiver_required", detail: "Accept the current host waiver.",
      }));
      return Promise.resolve({ registration_id: 7, status: "waitlisted" });
    });
    const { client, view } = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Review registration consent" }));
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    await screen.findByText(updated.body);
    await waitFor(() => expect(screen.getByRole("button", { name: "Save consent" })).toBeEnabled());
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    expect(attempts).toBe(1);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    await screen.findByText("Your registration consent has been updated.");
    expect(request).toHaveBeenLastCalledWith("venue", "/public/venue/events/event-one/register/", {
      method: "POST", body: JSON.stringify({ host_waiver_id: 5, host_waiver_version: "v3", host_waiver_accepted: true }),
    });
    view.unmount(); client.clear();
  });
});

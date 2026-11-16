import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OrganizationEventAdmission, organizationEligibilityKey } from "./OrganizationEventAdmission";
import type { PublicEventDetail } from "./eventTicketTypes";

const { identity, eligibility } = vi.hoisted(() => ({ identity: vi.fn(), eligibility: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"),
  getAccessToken: () => "test-session", memberRequest: identity, tenantMemberRequest: eligibility,
}));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in form</p> }));
vi.mock("../inventory/EventRegistrationForm", () => ({ EventRegistrationForm: ({ hostWaiver }: { hostWaiver: { version: string } | null }) => <p>Registration form {hostWaiver?.version}</p> }));

const event = { public_token: "event-one", registration_audience: "participating_organizations",
  registration_open: true, registration_requires_approval: false, availability: "Available",
} as PublicEventDetail;

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OrganizationEventAdmission event={event} makerspaceSlug="venue" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Check registration eligibility" }));
  return client;
}

describe("private organization eligibility", () => {
  beforeEach(() => { identity.mockReset(); eligibility.mockReset(); identity.mockResolvedValue({ id: 17 }); });
  afterEach(() => vi.useRealTimers());
  it("keys eligibility by account, tenant and event and opens only an eligible form", async () => {
    eligibility.mockResolvedValue({ eligible: true, reason: null, host_waiver: { id: 3, version: "v2", body: "Terms" } });
    const client = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Register" }));
    expect(screen.getByText("Registration form v2")).toBeInTheDocument();
    expect(eligibility).toHaveBeenCalledWith("venue", "/public/venue/events/event-one/eligibility/");
    expect(client.getQueryState(organizationEligibilityKey("venue", "event-one", 17))).toBeDefined();
    expect(organizationEligibilityKey("venue", "event-one", 18)).not.toEqual(organizationEligibilityKey("venue", "event-one", 17));
    client.clear();
  });
  it("does not offer Register to an ineligible account", async () => {
    eligibility.mockResolvedValue({ eligible: false, reason: "organization_audience_required", host_waiver: null });
    const client = setup(); await screen.findByText(/Registration requires active membership/);
    expect(screen.queryByRole("button", { name: "Register" })).not.toBeInTheDocument();
    client.clear();
  });
  it("shows failures and a retry action without exposing the form", async () => {
    eligibility.mockRejectedValue(new Error("Unavailable"));
    const client = setup(); await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText(/Registration form/)).not.toBeInTheDocument(); client.clear();
  });
  it("shows the imported audience block", async () => {
    eligibility.mockResolvedValue({ eligible: false, reason: "organization_audience_not_ready", host_waiver: null });
    const client = setup(); await screen.findByText(/Staff must review/); client.clear();
  });
  it("makes no idle requests for 16 cards and never polls checked or closed forms", async () => {
    eligibility.mockResolvedValue({ eligible: true, reason: null, host_waiver: null });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}>{Array.from({ length: 16 }, (_, id) =>
      <OrganizationEventAdmission key={id} event={{ ...event, public_token: `event-${id}` }} makerspaceSlug="venue" />,
    )}</QueryClientProvider>);
    vi.useFakeTimers();
    await act(() => vi.advanceTimersByTimeAsync(120_000));
    expect(identity).not.toHaveBeenCalled();
    expect(eligibility).not.toHaveBeenCalled();
    vi.useRealTimers();
    fireEvent.click(screen.getAllByRole("button", { name: "Check registration eligibility" })[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Register" }));
    vi.useFakeTimers();
    await act(() => vi.advanceTimersByTimeAsync(120_000));
    expect(eligibility).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Close form" }));
    await act(() => vi.advanceTimersByTimeAsync(120_000));
    expect(eligibility).toHaveBeenCalledTimes(1);
    view.unmount(); client.clear();
  });
});

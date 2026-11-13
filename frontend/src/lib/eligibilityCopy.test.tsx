import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "./api/errors";
import { eligibilityMessage, refusalCode } from "./eligibilityCopy";
import { MemberLoanRenew } from "../features/members/MemberLoanRenew";
import { MachineIntakeForm } from "../features/inventory/MachineIntakeForm";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("./api", async () => ({ ...await vi.importActual("./api"), memberRequest: request, tenantPublicRequest: request }));
vi.mock("../features/payments/PricePreview", () => ({ PricePreview: () => null }));

const refusal = (status: number, body: Record<string, unknown>) => new StructuredApiError(status, body);

describe("eligibility copy", () => {
  it("reads the code from both the string and the DRF list shape", () => {
    expect(refusalCode(refusal(403, { code: "membership_required" }))).toBe("membership_required");
    expect(refusalCode(refusal(400, { code: ["membership_lapsed"], detail: ["Renew."] }))).toBe("membership_lapsed");
    expect(refusalCode(new Error("plain"))).toBeUndefined();
  });

  it.each([
    ["membership_required", /active membership of this space.*ask space staff/],
    ["membership_inactive", /not active\. Ask space staff/],
    ["membership_lapsed", /term has ended\. Renew/],
    ["waiver_acceptance_required", /current waiver in your member area/],
    ["presence_required", /Check in at the space first/],
    ["borrower_restricted", /restricted at this space\. Talk to space staff/],
    ["member_restricted", /restricted at this space/],
    ["machine_intake_unavailable", /Ask space staff for help/],
    ["organization_audience_required", /participating organizations/],
    ["organization_audience_not_ready", /Staff must review/],
    ["organization_audience_disabled", /Contact the organizers/],
    ["organization_audience_changed", /Reload the page/],
    ["invitation_expired", /expired\. Ask an organization governor/],
    ["invitation_revoked", /withdrawn/],
    ["invitation_redeemed", /already been used/],
    ["invitation_grant_changed", /no longer holds all of the access/],
    ["organization_membership_suspended", /suspended\. Ask an organization governor/],
  ])("explains %s with a next step", (code, expected) => {
    expect(eligibilityMessage(refusal(403, { code, detail: "Raw server text." }))).toMatch(expected);
  });

  it("explains machine access refusals in words, with no training wording (decision 319)", () => {
    expect(eligibilityMessage(refusal(403, { code: "no_machine_access" })))
      .toBe("A space manager has not given you access to this machine yet. Ask space staff to give you access, then try again.");
    expect(eligibilityMessage(refusal(403, { code: "machine_access_expired" })))
      .toBe("Your access to this machine has ended. Ask space staff to renew it, then try again.");
    expect(eligibilityMessage(refusal(403, { code: "certification_required" }))).toBeNull();
  });

  it("leaves unrelated errors to the surface's own fallback", () => {
    expect(eligibilityMessage(refusal(409, { code: "booking_conflict", detail: "Taken." }))).toBeNull();
    expect(eligibilityMessage(refusal(400, { detail: "Bad." }))).toBeNull();
    expect(eligibilityMessage(new Error("network"))).toBeNull();
    expect(eligibilityMessage(null)).toBeNull();
  });
});

describe("member surfaces use the shared copy", () => {
  beforeEach(() => { request.mockReset(); });
  const client = () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

  it("loan renewal explains a lapsed membership sent in DRF's list shape", async () => {
    request.mockRejectedValue(refusal(400, { code: ["membership_lapsed"], detail: ["Renew your membership before extending this loan."] }));
    render(<QueryClientProvider client={client()}><MemberLoanRenew makerspaceId={7} makerspaceSlug="lab" requestId={12} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Renew loan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your membership term has ended. Renew your membership from your member area, then try again.");
  });

  it("loan renewal keeps other policy refusals as the server wrote them", async () => {
    request.mockRejectedValue(refusal(400, { code: ["renewal_limit"], detail: ["This loan has reached its renewal limit."] }));
    render(<QueryClientProvider client={client()}><MemberLoanRenew makerspaceId={7} makerspaceSlug="lab" requestId={12} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Renew loan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This loan has reached its renewal limit.");
  });

  it("machine service intake explains a missing check-in instead of the raw refusal", async () => {
    request.mockResolvedValueOnce({ materials: [], intake_schema: { version: 1, fields: [] } })
      .mockRejectedValueOnce(refusal(403, { code: "presence_required", detail: "An active presence session is required." }));
    render(<QueryClientProvider client={client()}><MachineIntakeForm available slug="lab" machineId={7} typeId={4} /></QueryClientProvider>);
    fireEvent.change(await screen.findByLabelText("Job title"), { target: { value: "Cut panel" } });
    fireEvent.click(screen.getByRole("button", { name: "Request work" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Check in at the space first (in your member area or at the front desk), then try again.");
    expect(alert).not.toHaveTextContent("An active presence session is required.");
  });
});

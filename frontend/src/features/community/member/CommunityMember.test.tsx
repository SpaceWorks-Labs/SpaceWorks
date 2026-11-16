import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { memberRequest, StructuredApiError } from "../../../lib/api";
import { GuardianConsentPanel } from "./GuardianConsentPanel";
import { JoinButton } from "./JoinButton";
import { MemberCommunityArea } from "./MemberCommunityArea";
import { VolunteerLog } from "./VolunteerLog";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn() }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

describe("GuardianConsentPanel", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); });

  it("e-signs the current text for a dependent", async () => {
    vi.mocked(memberRequest).mockImplementation(async (_path: string, options?: RequestInit) => options?.method ? {} : ({
      terms: { id: 1, version: "v2", body: "I agree to supervise.", is_active: true, created_at: "2026-10-01T00:00:00Z", superseded_at: null },
      dependents: [{ profile_id: 6, dependent_name: "Sam", consent_state: "none", consent_valid_until: null, consents: [] }],
    }));
    wrap(<GuardianConsentPanel makerspaceId={3} />);
    fireEvent.click(await screen.findByRole("button", { name: "Read and sign" }));
    expect(screen.getByText("I agree to supervise.")).toBeVisible();
    const sign = screen.getByRole("button", { name: "Sign consent" });
    expect(sign).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/give my consent as Sam's parent or guardian/));
    fireEvent.change(screen.getByLabelText("Type your full name to sign"), { target: { value: "Pat Young" } });
    fireEvent.click(sign);
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/guardian-consents/6/sign", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(vi.mocked(memberRequest).mock.calls.find(([, options]) => options?.method === "POST")![1]!.body as string);
    expect(body).toMatchObject({ signed_name: "Pat Young", accepted: true });
  });

  it("is absent for someone who is nobody's guardian", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ terms: null, dependents: [] });
    const { container } = wrap(<GuardianConsentPanel makerspaceId={3} />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});

describe("VolunteerLog", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); });

  it("logs hours for approval and shows waiting credits", async () => {
    vi.mocked(memberRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (options?.method === "POST") return {};
      if (path.endsWith("/volunteer-credits")) return [{ id: 1, member: 9, member_name: "Me", kind: "free_days", amount: "0", days: 7, currency: "", status: "available", minutes_converted: 300, applied_payment: null, applied_amount: null, applied_at: null, created_at: "2026-11-01T00:00:00Z" },
        { id: 3, member: 9, member_name: "Mia Member", kind: "discount", amount: "5.00", days: 0, currency: "EUR", status: "applied", minutes_converted: 120, applied_payment: 4, applied_amount: "5.00", applied_at: "2026-11-02T00:00:00Z", created_at: "2026-11-01T00:00:00Z" }];
      return [{ id: 2, member: 9, member_name: "Me", minutes: 60, worked_on: "2026-11-08", description: "", source: "manual", status: "pending", reviewed_at: null, review_note: "", created_at: "2026-11-08T00:00:00Z" }];
    });
    wrap(<VolunteerLog makerspaceId={3} />);
    expect(await screen.findByText("Waiting for approval")).toBeVisible();
    expect(await screen.findByText(/7 free days/)).toBeVisible();
    expect(screen.getByText(/Mia Member/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Minutes"), { target: { value: "45" } });
    fireEvent.change(screen.getByLabelText("Day"), { target: { value: "2026-11-09" } });
    fireEvent.click(screen.getByRole("button", { name: "Send for approval" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/volunteer-hours", { method: "POST", body: JSON.stringify({ minutes: 45, worked_on: "2026-11-09", description: "" }) }));
  });
});

describe("JoinButton", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); });

  it("checks the pass with join-prefill, then hands over to the membership request", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ name: "Grace", email: "grace@example.org", phone: "", source: "guest_pass", source_ref: 21, source_label: "Day pass" });
    wrap(<JoinButton makerspaceId={3} source={{ guest_pass_id: 21 }} memberHref="/m/x/member" />);
    fireEvent.click(screen.getByRole("button", { name: "Join as a member" }));
    expect(await screen.findByText(/apply as Grace \(grace@example.org\), after your day pass/)).toBeVisible();
    expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/join-prefill?guest_pass_id=21");
    expect(screen.getByRole("link", { name: "Continue to the membership request" })).toHaveAttribute("href", "/m/x/member#join-membership");
  });

  it("explains an existing membership", async () => {
    vi.mocked(memberRequest).mockRejectedValue(new StructuredApiError(409, { code: "already_member", detail: "raw" }));
    wrap(<JoinButton makerspaceId={3} source={{ registration_id: 4 }} memberHref="/member" />);
    fireEvent.click(screen.getByRole("button", { name: "Join as a member" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already a member");
  });
});

describe("MemberCommunityArea", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); vi.mocked(memberRequest).mockResolvedValue([]); });

  it("asks nothing of the server while every capability is off", () => {
    wrap(<MemberCommunityArea makerspaceId={3} memberBase="/member" features={[]} activeMember />);
    expect(memberRequest).not.toHaveBeenCalled();
  });

  it("offers Bring a guest to members and day passes to non-members", async () => {
    wrap(<MemberCommunityArea makerspaceId={3} memberBase="/member" features={["membership.guest_passes", "membership.day_passes"]} activeMember />);
    expect(await screen.findByRole("heading", { name: "Bring a guest" })).toBeVisible();
    expect(memberRequest).not.toHaveBeenCalledWith("/member/makerspaces/3/day-passes");
  });
});

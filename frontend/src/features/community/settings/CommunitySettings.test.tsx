import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import { communitySettingsSections } from "./communitySettingsSections";
import { CommunityPolicySettings } from "./CommunityPolicySettings";
import { GuestWaiverSettings } from "./GuestWaiverSettings";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const policy = {
  minors_admitted: false, minors_minimum_age: 13, adult_age: 18, guardian_must_be_present: true, minors_may_borrow: false,
  minors_may_use_machines: false, consent_valid_days: 365, volunteer_minutes_per_credit: 0, volunteer_credit_kind: "discount",
  volunteer_credit_amount: "0.00", volunteer_credit_days: 0, join_followup_enabled: false, join_followup_delay_hours: 24,
};

describe("communitySettingsSections", () => {
  const space = (features: string[]) => ({ id: 3, enabled_modules: ["membership"], enabled_features: features });
  it("adds Guest passes and Community only for the Space Manager and only while switched on", () => {
    expect(communitySettingsSections(space([]), true)).toEqual([]);
    expect(communitySettingsSections(space(["membership.guest_passes", "membership.join_funnel"]), true).map((row) => row.id)).toEqual(["guest-passes", "visitor-waiver", "community"]);
    expect(communitySettingsSections(space(["membership.guest_passes"]), false)).toEqual([]);
    expect(communitySettingsSections({ id: 3, enabled_modules: [], enabled_features: ["membership.minors"] }, true)).toEqual([]);
  });

  it("keeps the visitor waiver reachable while guest passes are off (EV-25)", () => {
    const presence = { id: 3, enabled_modules: ["membership", "presence"], enabled_features: [] };
    expect(communitySettingsSections(presence, true).map((row) => row.id)).toEqual(["visitor-waiver"]);
    expect(communitySettingsSections(presence, false)).toEqual([]);
  });
});

describe("GuestWaiverSettings", () => {
  const guestPolicy = { guest_borrowing_mode: "none", guest_machine_mode: "none", sponsored_liability: "guest", walk_in_registration_creates: "guest_pass",
    waiver_required_on_site: true, waiver_gate_without_passes: false, sponsor_min_tenure_days: 0, max_concurrent_guests_per_sponsor: 2,
    sponsor_must_be_present: false, visits_before_join_prompt: 3, hard_visit_cap: null, day_pass_daily_cap: null };
  beforeEach(() => {
    vi.mocked(staffRequest).mockReset();
    vi.mocked(staffRequest).mockImplementation(async (_path: string, options?: RequestInit) => options?.method === "PATCH" ? { ...guestPolicy, ...JSON.parse(options.body as string) } : guestPolicy);
  });

  it("turns the gate on with passes off and sends only the two waiver switches", async () => {
    render(<QueryClientProvider client={new QueryClient()}><GuestWaiverSettings makerspaceId={3} passesOn={false} /></QueryClientProvider>);
    fireEvent.click(await screen.findByRole("switch", { name: "Ask for the waiver while guest passes are off" }));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-pass-policy",
      { method: "PATCH", body: JSON.stringify({ waiver_required_on_site: true, waiver_gate_without_passes: true }) }));
  });

  it("shows a load error with a retry", async () => {
    vi.mocked(staffRequest).mockRejectedValueOnce(new Error("Policy unavailable"));
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><GuestWaiverSettings makerspaceId={3} passesOn /></QueryClientProvider>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Policy unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("switch", { name: "Require the waiver" })).toBeChecked();
  });
});

describe("CommunityPolicySettings", () => {
  beforeEach(() => {
    vi.mocked(staffRequest).mockReset();
    vi.mocked(staffRequest).mockImplementation(async (_path: string, options?: RequestInit) => options?.method === "PATCH" ? { ...policy, ...JSON.parse(options.body as string) } : policy);
  });

  it("shows only the switched-on groups and sends only what changed", async () => {
    render(<QueryClientProvider client={new QueryClient()}><CommunityPolicySettings makerspaceId={3} flags={{ minors: true, volunteer: false, joinFunnel: true }} /></QueryClientProvider>);
    fireEvent.click(await screen.findByLabelText("Admit people under the adult age"));
    expect(screen.queryByText("Volunteer credit")).toBeNull();
    fireEvent.change(screen.getByLabelText("Hours after the event"), { target: { value: "48" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/community-policy",
      { method: "PATCH", body: JSON.stringify({ minors_admitted: true, join_followup_delay_hours: 48 }) }));
  });
});

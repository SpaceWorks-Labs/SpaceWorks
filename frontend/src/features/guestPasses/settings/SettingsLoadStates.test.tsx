import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import { CommunityPolicySettings } from "../../community/settings/CommunityPolicySettings";
import { GuestWaiverSettings } from "../../community/settings/GuestWaiverSettings";
import { DayPassProductsSettings } from "./DayPassProductsSettings";
import { GuestPassPolicySettings } from "./GuestPassPolicySettings";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
const never = () => new Promise<never>(() => undefined);
const guestPolicy = { guest_borrowing_mode: "none", guest_machine_mode: "none", sponsored_liability: "guest", walk_in_registration_creates: "guest_pass",
  waiver_required_on_site: true, waiver_gate_without_passes: false, sponsor_min_tenure_days: 0, max_concurrent_guests_per_sponsor: 2,
  sponsor_must_be_present: false, visits_before_join_prompt: 3, hard_visit_cap: null, day_pass_daily_cap: null };

beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

describe("guest-pass and community settings loading and error states (EV-24 / C20)", () => {
  it.each([
    ["guest pass rules", () => wrap(<GuestPassPolicySettings makerspaceId={3} />), /Loading guest pass rules/],
    ["day passes", () => wrap(<DayPassProductsSettings makerspaceId={3} />), /Loading day passes/],
    ["community settings", () => wrap(<CommunityPolicySettings makerspaceId={3} flags={{ minors: true, volunteer: true, joinFunnel: true }} />), /Loading community settings/],
    ["the waiver rule", () => wrap(<GuestWaiverSettings makerspaceId={3} passesOn />), /Loading the waiver rule/],
  ])("shows a polite loading status while %s load, with no form controls", (_name, mount, text) => {
    vi.mocked(staffRequest).mockImplementation(never);
    mount();
    expect(screen.getByRole("status")).toHaveTextContent(text);
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
  });

  it.each([
    ["day passes", () => wrap(<DayPassProductsSettings makerspaceId={3} />)],
    ["community settings", () => wrap(<CommunityPolicySettings makerspaceId={3} flags={{ minors: true, volunteer: true, joinFunnel: true }} />)],
  ])("shows an alert with the server message when %s fail to load", async (_name, mount) => {
    vi.mocked(staffRequest).mockRejectedValue(new Error("Backend down"));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend down");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("surfaces a failed save of the guest pass rules without losing the edit", async () => {
    vi.mocked(staffRequest).mockImplementation(async (_path: string, options?: RequestInit) => {
      if (options?.method === "PATCH") throw new Error("Version conflict");
      return guestPolicy;
    });
    wrap(<GuestPassPolicySettings makerspaceId={3} />);
    const borrowing = await screen.findByRole("combobox", { name: "Guest borrowing" });
    fireEvent.change(borrowing, { target: { value: "full_with_deposit" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Version conflict");
    expect(screen.getByRole("combobox", { name: "Guest borrowing" })).toHaveValue("full_with_deposit");
  });
});

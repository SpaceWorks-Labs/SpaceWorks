import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MembershipPlansSection } from "./MembershipPlansSection";
import { emptyRules, rulesInput, validateRules } from "./MembershipPlanRulesFields";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

function wrap(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string, options?: RequestInit) =>
    Promise.resolve(options?.method ? { id: 9 } : path.endsWith("/membership-plans") ? [] : []));
});

describe("plan rules (G16, X5)", () => {
  it("validates fixed dates, money and the lapse days", () => {
    expect(validateRules({ ...emptyRules, plan_type: "fixed_end" })).toMatch(/end date/);
    // 0.12.0: three decimals are allowed (KWD, BHD); a fourth is not.
    expect(validateRules({ ...emptyRules, renewal_amount: "1.2345" })).toMatch(/renewal price/);
    expect(validateRules({ ...emptyRules, rejoin_rule: "after_lapse" })).toMatch(/lapse/);
    expect(validateRules({ ...emptyRules, slug: "Bad Slug" })).toMatch(/link name/);
    expect(validateRules(emptyRules)).toBeNull();
  });

  it("sends only the fields whose switch is on", () => {
    expect(rulesInput(emptyRules, false, false)).toEqual({ sort_order: 0 });
    const on = rulesInput({ ...emptyRules, plan_type: "lifetime", is_public: true, slug: "life" }, true, true);
    expect(on).toMatchObject({ plan_type: "lifetime", auto_renew: false, is_public: true, slug: "life" });
  });

  it("hides the type switch while plan rules are off and explains each type when on", async () => {
    const { unmount } = wrap(<MembershipPlansSection makerspaceId={3} features={[]} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(screen.queryByRole("radiogroup", { name: "Plan type" })).toBeNull();
    unmount();
    wrap(<MembershipPlansSection makerspaceId={3} features={["membership.plan_rules"]} />);
    fireEvent.click(await screen.findByRole("radio", { name: "Financial year" }));
    expect(screen.getByText(/financial year ends/)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Plan name"), { target: { value: "FY plan" } });
    fireEvent.click(screen.getByRole("button", { name: "Create plan" }));
    await waitFor(() => {
      const call = staffRequest.mock.calls.find(([, options]) => options?.method === "POST");
      expect(JSON.parse(call![1].body).plan_type).toBe("financial_year");
    });
  });
});

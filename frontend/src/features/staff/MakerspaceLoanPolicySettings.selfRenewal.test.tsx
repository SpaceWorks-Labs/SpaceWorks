import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { MakerspaceLoanPolicySettings, type LoanPolicy } from "./MakerspaceLoanPolicySettings";

const { query, request } = vi.hoisted(() => ({ query: vi.fn(), request: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: request }));
vi.mock("./panels/shared", () => ({ useStaffGet: query }));
const policy: LoanPolicy = {
  id: 7, default_loan_days: 7, loan_renewal_mode: "auto", loan_max_renewals: 1, loan_renewal_days: 7,
  loan_max_active: 0, loan_max_items: 0, loan_reminder_offsets_hours: [0], loan_escalate_overdue_days: 0, account_self_renewal: false,
};
const SWITCH = "Borrowers renew their own loans";

beforeEach(() => { query.mockReset(); request.mockReset(); query.mockReturnValue({ data: policy, error: null }); });

function setup({ modules = ["member_accounts"], manage = true, features = ["loans.renewals"] } = {}) {
  render(<QueryClientProvider client={new QueryClient()}><MakerspaceLoanPolicySettings makerspaceId={7}
    enabledFeatures={features} enabledModules={modules} canManageMakerspace={manage} /></QueryClientProvider>);
}

it("lets the Space Manager turn on self-renewal for account-only borrowers", async () => {
  request.mockResolvedValue({ ...policy, account_self_renewal: true });
  setup();
  fireEvent.click(screen.getByRole("switch", { name: new RegExp(SWITCH) }));
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/return-policy", {
    method: "PATCH", body: JSON.stringify({ ...policy, account_self_renewal: true }) }));
});

it("hides the switch from anyone but the Space Manager", () => {
  setup({ manage: false });
  expect(screen.queryByText(SWITCH)).toBeNull();
});

it("hides the switch when membership runs, member accounts are off or renewals are off", () => {
  const { unmount } = render(<QueryClientProvider client={new QueryClient()}><MakerspaceLoanPolicySettings makerspaceId={7}
    enabledFeatures={["loans.renewals"]} enabledModules={["member_accounts", "membership"]} canManageMakerspace /></QueryClientProvider>);
  expect(screen.queryByText(SWITCH)).toBeNull();
  unmount();
  setup({ modules: [] });
  expect(screen.queryByText(SWITCH)).toBeNull();
});

it("hides the switch while renewals are switched off for the space", () => {
  setup({ features: [] });
  expect(screen.queryByText(SWITCH)).toBeNull();
});

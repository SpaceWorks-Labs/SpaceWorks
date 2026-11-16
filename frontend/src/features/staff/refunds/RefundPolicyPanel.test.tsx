import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RefundPolicyPanel } from "./RefundPolicyPanel";
import { policyBody } from "./RefundPolicyCard";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const base = { plan: null, plan_name: "", currency: "usd", updated_at: "2026-10-20T10:00:00Z", full_within_days: 0,
  partial_mode: "percent" };
const policies = [
  { ...base, area: "events", configured: true, full_before_minutes: 2880, partial_before_minutes: 1440,
    partial_percent: 50, cancellation_fee: "2.00" },
  { ...base, area: "bookings", configured: false, full_before_minutes: 0, partial_before_minutes: 0,
    partial_percent: 0, cancellation_fee: "0.00" },
  { ...base, area: "membership", configured: true, full_before_minutes: 0, partial_before_minutes: 0,
    full_within_days: 14, partial_mode: "pro_rata", partial_percent: 0, cancellation_fee: "0.00" },
  { ...base, area: "membership", plan: 5, plan_name: "Annual", configured: true, full_within_days: 30,
    partial_mode: "percent", partial_percent: 25, cancellation_fee: "5.00", full_before_minutes: 0, partial_before_minutes: 0 },
];
const plans = [{ id: 5, name: "Annual", currency: "usd" }, { id: 6, name: "Monthly", currency: "usd" }];

function renderPanel(canEdit: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><RefundPolicyPanel makerspaceId={7} canEdit={canEdit} /></QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string, options?: { method?: string }) =>
    Promise.resolve(options?.method ? policies[1] : path.includes("membership-plans") ? plans : policies));
});

describe("RefundPolicyPanel", () => {
  it("shows events, bookings and the membership default with its plan rules", async () => {
    renderPanel(false);
    expect(await screen.findByText("2 days before")).toBeInTheDocument();
    expect(screen.getByText(/A \$2\.00 fee is kept/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Memberships" })).toBeInTheDocument();
    expect(screen.getByText("within 14 days of the term start")).toBeInTheDocument();
    expect(screen.getByText("The unused part of the term")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Plan: Annual" })).toBeInTheDocument();
    expect(screen.getByText("25% refund")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Set a policy|Edit policy/ })).not.toBeInTheDocument();
  });

  it("saves hours as minutes and refuses a partial window wider than the full one", async () => {
    renderPanel(true);
    fireEvent.click(await screen.findByRole("button", { name: "Set a policy" }));
    fireEvent.change(screen.getByLabelText(/Full refund if cancelled at least/), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText(/Partial refund if cancelled at least/), { target: { value: "24" } });
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/partial window/);
    fireEvent.change(screen.getByLabelText(/Partial refund if cancelled at least/), { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/refund-policies/bookings",
      expect.objectContaining({ method: "PUT" })));
    const call = staffRequest.mock.calls.find(([, options]) => options?.method === "PUT")!;
    expect(JSON.parse(call[1].body)).toMatchObject({ full_before_minutes: 720, partial_before_minutes: 360, partial_mode: "percent" });
  });

  it("adds a per-plan membership rule with a pro-rata refund", async () => {
    renderPanel(true);
    const picker = await screen.findByLabelText("Add a rule for one plan");
    expect(within(picker).queryByRole("option", { name: "Annual" })).not.toBeInTheDocument();
    fireEvent.change(picker, { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText(/within \(days of the term start\)/), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/refund-policies/membership/plans/6",
      expect.objectContaining({ method: "PUT" })));
    const call = staffRequest.mock.calls.find(([path]) => String(path).endsWith("/plans/6"))!;
    expect(JSON.parse(call[1].body)).toMatchObject({ full_within_days: 7, partial_mode: "pro_rata", full_before_minutes: 0 });
  });

  it("validates the form shape for both kinds of area", () => {
    const form = { full: "48", partial: "24", percent: "50", days: "10", fee: "1.50" };
    expect(policyBody(false, form, "percent")[0]).toMatchObject({ full_before_minutes: 2880, partial_mode: "percent", full_within_days: 0 });
    expect(policyBody(true, form, "percent")[0]).toMatchObject({ full_within_days: 10, partial_percent: 50, full_before_minutes: 0 });
    expect(policyBody(true, { ...form, days: "-1" }, "pro_rata")[1]).toMatch(/whole/);
    expect(policyBody(false, { ...form, fee: "1.2345" }, "percent")[1]).toMatch(/decimals/);
  });
});

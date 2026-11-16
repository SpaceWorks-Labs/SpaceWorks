import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformSpacesPanel } from "./PlatformSpacesPanel";
import type { BillingSettings, HostingInvoice, HostingPlan } from "./plansApi";

const { staffRequest, publicV1Request } = vi.hoisted(() => ({ staffRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request }));

const PLAN: HostingPlan = { id: 2, key: "starter", name: "Starter", description: "", is_active: true, trial_days: 14, price_minor: 2500,
  currency: "USD", billing_period: "monthly", limits: { members: 100, storage: 1024 * 1024 * 512 }, allowed_modules: [], space_count: 3,
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const INVOICE: HostingInvoice = { id: 5, number: "INV-0005", makerspace: { id: 7, name: "North Lab" }, makerspace_name: "North Lab",
  description: "November hosting", amount_minor: 2500, currency: "USD", due_on: "2026-11-30", period_start: null, period_end: null,
  status: "open", overdue: false, paid_at: null, voided_at: null, void_reason: "", receipts: [], online_payable: false, created_at: "2026-11-01T00:00:00Z" };
const BILLING: BillingSettings = { auto_enforce_enabled: false, grace_days: 14, online_billing_switch: false, provider: "stripe",
  stripe_secret_key_set: true, stripe_webhook_secret_set: false, razorpay_key_id: "", razorpay_key_secret_set: false,
  razorpay_webhook_secret_set: false, updated_at: "2026-11-01T00:00:00Z" };
const CARD = { id: 7, name: "North Lab", slug: "north-lab", public_code: "NL", state: "active", created_at: "2026-01-01T00:00:00Z",
  lifecycle_state: "active", archived_at: null, suspended: null, read_only: null, schedule: null, usage: { managed: true, resources: [] },
  usage_peak_percent: null, last_activity_at: null, backups: { last_backed_up_at: null, last_drill: null },
  security: { blocked_accounts: 0, locked_settings: 0 }, open_issues: 0, modules: [], managers: [], plan: null };
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

function setup(config: Record<string, unknown>) {
  publicV1Request.mockResolvedValue(config);
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "PATCH" && path.includes("billing")) return { ...BILLING, updated_at: "2026-11-02T00:00:00Z" };
    if (init?.method) return {};
    if (path.startsWith("/admin/platform/space-health")) return page([CARD]);
    if (path === "/admin/platform/spaces/7/plan") return null;
    if (path.startsWith("/admin/platform/hosting-plans")) return [PLAN];
    if (path.startsWith("/admin/platform/hosting-invoices")) return page([INVOICE]);
    if (path.startsWith("/admin/platform/hosting-billing-settings")) return BILLING;
    return page([]);
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PlatformSpacesPanel /></QueryClientProvider>);
}

function sent(path: string, method: string) {
  const call = staffRequest.mock.calls.find(row => row[0] === path && (row[1] as RequestInit | undefined)?.method === method);
  return call ? JSON.parse((call[1] as RequestInit).body as string) : undefined;
}

beforeEach(() => { staffRequest.mockReset(); publicV1Request.mockReset(); });

describe("PlatformSpacesPanel", () => {
  it("renders nothing of the limiter without managed_plans in /config", async () => {
    setup({});
    expect(await screen.findByRole("heading", { name: "Health" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Onboarding" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Announcements" })).toBeInTheDocument();
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    expect(screen.queryByRole("heading", { name: "Plans" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Billing" })).not.toBeInTheDocument();
    expect(staffRequest.mock.calls.some(([path]) => String(path).includes("hosting-plans"))).toBe(false);
  });

  it("offers Create space and the Space Managers' requests (0.12.0)", async () => {
    setup({});
    expect(await screen.findByRole("heading", { name: "Requests" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create space" })).toBeInTheDocument();
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).startsWith("/admin/platform/archive-requests"))).toBe(true));
  });

  it("shows plans and billing when managed_plans is present", async () => {
    setup({ managed_plans: { enabled: true, online_billing: false } });
    expect(await screen.findByRole("heading", { name: "Plans" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Billing" })).toBeInTheDocument();
    expect(await screen.findByText("Starter")).toBeInTheDocument();
    expect(await screen.findByText(/INV-0005/)).toBeInTheDocument();
    expect(await screen.findByText("Saved. Type a new value to replace it.")).toBeInTheDocument();
  });

  it("creates a plan with storage converted from MiB to bytes", async () => {
    setup({ managed_plans: { enabled: true, online_billing: false } });
    fireEvent.click(await screen.findByRole("button", { name: "New plan" }));
    const form = screen.getByRole("form", { name: "New plan" });
    fireEvent.change(within(form).getByRole("textbox", { name: "Name" }), { target: { value: "Pro" } });
    fireEvent.change(within(form).getByRole("textbox", { name: /^Short name/ }), { target: { value: "pro" } });
    fireEvent.change(within(form).getByRole("spinbutton", { name: /^Storage \(MB\)/ }), { target: { value: "2" } });
    fireEvent.change(within(form).getByRole("spinbutton", { name: "Price" }), { target: { value: "49.50" } });
    fireEvent.click(within(form).getByRole("button", { name: "Create plan" }));
    await waitFor(() => expect(sent("/admin/platform/hosting-plans", "POST")).toMatchObject({ key: "pro", name: "Pro", price_minor: 4950,
      limits: { storage: 2 * 1024 * 1024, members: null }, allowed_modules: [] }));
  });

  it("picks a plan's allowed modules from translated checkboxes and sends their keys", async () => {
    setup({ managed_plans: { enabled: true, online_billing: false } });
    fireEvent.click(await screen.findByRole("button", { name: "New plan" }));
    const form = screen.getByRole("form", { name: "New plan" });
    fireEvent.change(within(form).getByRole("textbox", { name: "Name" }), { target: { value: "Pro" } });
    fireEvent.change(within(form).getByRole("textbox", { name: /^Short name/ }), { target: { value: "pro" } });
    const features = within(form).getByRole("group", { name: "Features this plan includes" });
    fireEvent.click(within(features).getByRole("checkbox", { name: "Events" }));
    fireEvent.click(within(features).getByRole("checkbox", { name: "Bookings" }));
    expect(features).toHaveTextContent("Included: Events, Bookings.");
    fireEvent.click(within(features).getByRole("checkbox", { name: "Events" }));
    fireEvent.click(within(form).getByRole("button", { name: "Create plan" }));
    await waitFor(() => expect(sent("/admin/platform/hosting-plans", "POST")).toMatchObject({ key: "pro", allowed_modules: ["bookings"] }));
  });

  it("records an offline payment on an open invoice", async () => {
    setup({ managed_plans: { enabled: true, online_billing: false } });
    fireEvent.click(await screen.findByRole("button", { name: "Record payment for INV-0005" }));
    const dialog = await screen.findByRole("dialog", { name: "Record payment for INV-0005" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: /Reference/ }), { target: { value: "UTR123" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record payment" }));
    await waitFor(() => expect(sent("/admin/platform/hosting-invoices/5/record-payment", "POST")).toMatchObject({ method: "bank_transfer", reference: "UTR123" }));
  });

  it("assigns a plan with a trial from a space's Manage menu", async () => {
    setup({ managed_plans: { enabled: true, online_billing: false } });
    fireEvent.click(within(await screen.findByRole("article", { name: "North Lab" })).getByRole("button", { name: "Manage" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: /^Plan/ }));
    const dialog = await screen.findByRole("dialog", { name: "Plan for North Lab" });
    const select = within(dialog).getByRole("combobox", { name: "Plan" });
    await within(select).findByRole("option", { name: "Starter" });
    fireEvent.change(select, { target: { value: "2" } });
    fireEvent.change(within(dialog).getByRole("spinbutton", { name: /Trial days/ }), { target: { value: "30" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save plan" }));
    await waitFor(() => expect(sent("/admin/platform/spaces/7/plan", "PUT")).toEqual({ plan_id: 2, trial_days: 30 }));
  });

  it("sends only typed secrets when saving billing settings", async () => {
    setup({ managed_plans: { enabled: true, online_billing: false } });
    const form = await screen.findByRole("form", { name: "Billing settings" });
    fireEvent.change(within(form).getByLabelText("Stripe webhook secret"), { target: { value: "whsec_test" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save billing settings" }));
    await waitFor(() => expect(sent("/admin/platform/hosting-billing-settings", "PATCH")).toEqual({ auto_enforce_enabled: false, grace_days: 14,
      provider: "stripe", razorpay_key_id: "", stripe_webhook_secret: "whsec_test" }));
  });
});

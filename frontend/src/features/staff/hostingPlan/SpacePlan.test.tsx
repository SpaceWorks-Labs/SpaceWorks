import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TenantUsagePanel } from "../TenantUsagePanel";
import type { Makerspace } from "../panels/shared";
import type { SpacePlanUsage } from "./spacePlanApi";

const { staffRequest, publicV1Request } = vi.hoisted(() => ({ staffRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request }));

const PLAN: SpacePlanUsage = {
  plan: { key: "starter", name: "Starter", description: "For small spaces." }, trial_ends_at: "2026-12-01T00:00:00Z", read_only_reason: null,
  resources: [
    { key: "members", label: "Members", used: 40, limit: 100, unit: "count", percent: 40, level: "ok" },
    { key: "machines", label: "Machines", used: 8, limit: 10, unit: "count", percent: 80, level: "warning" },
    { key: "events_monthly", label: "Events this month", used: 5, limit: 5, unit: "count", percent: 100, level: "limit" },
  ],
  warnings: ["Machines are at 80% of your plan."],
};
const INVOICE = { id: 5, number: "INV-0005", makerspace: null, makerspace_name: "North Lab", description: "", amount_minor: 2500, currency: "USD",
  due_on: "2026-11-30", period_start: null, period_end: null, status: "open", overdue: true, paid_at: null, voided_at: null, void_reason: "",
  receipts: [], online_payable: true, created_at: "2026-11-01T00:00:00Z" };

function setup(config: Record<string, unknown>) {
  publicV1Request.mockResolvedValue(config);
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") return { url: "https://pay.example.com/session/1" };
    if (path.endsWith("/hosting-plan")) return PLAN;
    if (path.endsWith("/hosting-invoices")) return [INVOICE];
    return { makerspace_id: 7, managed: true, resources: [] };
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <TenantUsagePanel makerspace={{ id: 7, name: "North Lab", slug: "north-lab", public_code: "NL" } as Makerspace} />
  </QueryClientProvider>);
}

const assign = vi.fn();
beforeEach(() => {
  staffRequest.mockReset(); publicV1Request.mockReset(); assign.mockReset();
  vi.stubGlobal("location", { ...window.location, assign, pathname: "/admin/usage", search: "" });
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("Space Manager plan usage", () => {
  it("shows no plan without managed_plans, but still lists the limits by area (decisions 281/284 apply to every space)", async () => {
    setup({});
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/config"));
    await screen.findByRole("heading", { name: "Usage & limits" });
    expect(screen.queryByRole("heading", { name: "Starter" })).not.toBeInTheDocument();
    expect(await screen.findByRole("progressbar", { name: "Members used" })).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/hosting-plan");
  });

  it("shows each limit's level, the warnings and the trial end", async () => {
    setup({ managed_plans: { enabled: true, online_billing: true } });
    expect(await screen.findByRole("heading", { name: "Starter" })).toBeInTheDocument();
    expect(screen.getByText("Machines are at 80% of your plan.")).toBeInTheDocument();
    expect(screen.getByText("Near limit")).toBeInTheDocument();
    expect(screen.getByText("At limit")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "New events this month used" })).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByRole("progressbar", { name: "Members used" })).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText(/Trial ends/)).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/hosting-plan");
  });

  it("keeps the visible payment action in its accessible name and names the invoice", async () => {
    setup({ managed_plans: { enabled: true, online_billing: true } });
    expect(await screen.findByText("Pay online", { selector: "button", exact: true })).toHaveAccessibleName(/^Pay online INV-0005$/);
  });

  it("keeps the visible opening action named while payment starts", async () => {
    setup({ managed_plans: { enabled: true, online_billing: true } });
    const pay = await screen.findByText("Pay online", { selector: "button", exact: true });
    staffRequest.mockImplementationOnce(() => new Promise(() => {}));
    fireEvent.click(pay);
    const opening = await screen.findByText("Opening…", { selector: "button", exact: true });
    expect(opening).toHaveAccessibleName(/^Opening… INV-0005$/);
    expect(opening).toBeDisabled();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/hosting-invoices/5/checkout", { method: "POST", body: "{}" });
  });

  it("pays an open invoice online by redirecting to the checkout", async () => {
    setup({ managed_plans: { enabled: true, online_billing: true } });
    const row = (await screen.findByText(/INV-0005 ·/)).closest("div.relative") as HTMLElement;
    expect(within(row).getByText("Overdue")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pay online INV-0005" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/hosting-invoices/5/checkout", { method: "POST", body: "{}" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://pay.example.com/session/1"));
  });

  it("offers no online payment when the invoice is not payable online", async () => {
    INVOICE.online_payable = false;
    setup({ managed_plans: { enabled: true, online_billing: false } });
    expect(await screen.findByText(/INV-0005 ·/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pay online INV-0005" })).not.toBeInTheDocument();
    INVOICE.online_payable = true;
  });

  it("groups the space quotas and platform use by area with their levels, read-only", async () => {
    const quotas = { ...PLAN, plan: null, hosted: false, resources: [], warnings: [],
      space_quota_resources: [{ key: "bookings_monthly", label: "bookings created this month", used: 9, limit: 10, unit: "count", percent: 90, level: "warning", area: "bookings" }],
      platform_resources: [{ key: "platform_sms_monthly", label: "sms", used: 50, limit: 50, unit: "count", percent: 100, level: "limit", area: "messaging" },
        { key: "platform_email_monthly", label: "email", used: 3, limit: null, unit: "count", percent: null, level: "ok", area: "messaging" }] };
    publicV1Request.mockResolvedValue({});
    staffRequest.mockImplementation(async (path: string) => path.endsWith("/hosting-plan") ? quotas : { makerspace_id: 7, managed: false, resources: [] });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TenantUsagePanel makerspace={{ id: 7, name: "North Lab", slug: "north-lab", public_code: "NL" } as Makerspace} />
    </QueryClientProvider>);
    const bookings = (await screen.findByRole("heading", { name: "Bookings" })).closest("section")!;
    expect(within(bookings).getByText("New bookings this month")).toBeInTheDocument();
    expect(within(bookings).getByText("Near limit")).toBeInTheDocument();
    const messaging = screen.getByRole("heading", { name: "Messaging" }).closest("section")!;
    expect(within(messaging).getByText("At limit")).toBeInTheDocument();
    expect(within(messaging).getByText(/Using 3 · no limit/)).toBeInTheDocument();
    expect(within(messaging).getByRole("progressbar", { name: "Texts through the platform this month used" })).toHaveAttribute("aria-valuenow", "100");
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});

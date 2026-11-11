import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StaffListContext } from "../StaffListContext";
import { PaymentsPanel } from "../PaymentsPanel";
import type { AreaKey, AreaQueueRow } from "./areaPaymentsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const row = (patch: Partial<AreaQueueRow> = {}): AreaQueueRow => ({
  id: 61, subject_type: "machine_session", subject_id: 4, subject_label: "Laser session", status: "pending",
  amount: "15.00", currency: "usd", refunded_amount: "0.00", refunds: [], created_at: "2026-11-01T10:00:00Z",
  updated_at: "2026-11-01T10:00:00Z", area: "machines", member_id: 12, ...patch,
});
const groups = [
  { area: "machines", pending: 2, overdue: 1, claims: 1, owed: { usd: "30.00" } },
  { area: "lending", pending: 1, overdue: 0, claims: 0, owed: { inr: "300.00" } },
];
const claim = { id: 8, payment_id: 61, subject_label: "Laser session", method: "upi", reference: "UTR123", paid_on: "2026-11-09",
  amount: "15.00", currency: "usd", status: "submitted", decision_note: "", decided_at: null, created_at: "2026-11-09T10:00:00Z", via_pay_link: false };

let rows: AreaQueueRow[];
let postResult: unknown;
beforeEach(() => {
  rows = [row()];
  postResult = row({ status: "paid_offline" });
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    if (options?.method === "POST") return typeof postResult === "function" ? (postResult as (p: string) => unknown)(path) : postResult;
    if (path.includes("area-queue/summary")) return { groups };
    if (path.includes("area-queue/claims")) return { count: 1, next: null, previous: null, results: [claim] };
    if (path.includes("saved-views")) return { count: 0, next: null, previous: null, results: [] };
    return { count: rows.length, next: null, previous: null, results: rows };
  });
});

function mount(actions: string[], { features = [] as string[], area, entry = "/" }: { features?: string[]; area?: AreaKey; entry?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<MemoryRouter initialEntries={[entry]}><QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "x", canShare: false, actions, makerspace: { id: 7, enabled_modules: [], enabled_features: features } }}>
      <PaymentsPanel makerspaceId={7} makerspaceName="Lab" actorActions={actions} area={area} embedded={Boolean(area)} />
    </StaffListContext.Provider></QueryClientProvider></MemoryRouter>);
}
const gets = () => staffRequest.mock.calls.filter(([, options]) => !options).map(([path]) => String(path));

describe("own-area Payments queue (decision 242 a/b)", () => {
  it("reads area-queue for a Machine Manager, with per-area totals and no finance surfaces", async () => {
    mount(["manage_machines"]);
    await screen.findByText("Laser session");
    expect(gets().some(path => path.startsWith("/admin/makerspace/7/payments/area-queue?status=pending"))).toBe(true);
    expect(gets().some(path => /\/payments\?/.test(path))).toBe(false);
    const machines = screen.getByRole("button", { name: "Machines: 2 to collect" });
    expect(within(machines).getByText("1 overdue")).toBeVisible();
    // Decision 247: the lending key is shown as Inventory.
    expect(screen.getByRole("button", { name: "Inventory: 1 to collect" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Billing documents" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Subject" })).toBeNull();
    expect(screen.getByText(/Charges for the areas you run, owed to Lab/)).toBeVisible();
  });

  it("settles with a receipt through the existing mark-offline route", async () => {
    mount(["manage_machines"]);
    await screen.findByText("Laser session");
    fireEvent.click(screen.getByRole("button", { name: "Mark paid" }));
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments/61/mark-offline", expect.objectContaining({ method: "POST" })));
  });

  it("says a second person must confirm when the two-person check is on", async () => {
    postResult = row();
    mount(["manage_machines"], { features: ["billing.maker_checker"] });
    await screen.findByText("Laser session");
    expect(screen.getByText("Two-person check is on.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Mark paid" }));
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));
    expect(await screen.findByText(/counts as paid once a second person/)).toBeVisible();
  });

  it("shows a waiting row instead of Mark paid while a settlement awaits its checker", async () => {
    rows = [row({ ledger_flags: { method_label: "", awaiting_confirmation_id: 3, open_claim_id: null, open_flags: 0, disputed: false, taxed: false, pay_link_available: false } })];
    mount(["manage_machines"]);
    expect(await screen.findByText("Waiting for a second person")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Mark paid" })).toBeNull();
  });

  it("sends a reminder for an account's charge and explains a refusal", async () => {
    mount(["manage_machines"]);
    await screen.findByText("Laser session");
    fireEvent.click(screen.getByRole("button", { name: "Actions for Laser session" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Send reminder" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments/61/area-reminder", { method: "POST" }));
    expect(await screen.findByText("Reminder sent to the payer's email.")).toBeVisible();
  });

  it("offers no reminder for an account-less charge and creates its pay link through the area route", async () => {
    rows = [row({ member_id: null, ledger_flags: { method_label: "", awaiting_confirmation_id: null, open_claim_id: null, open_flags: 0, disputed: false, taxed: false, pay_link_available: true } })];
    postResult = { url: "https://pay.example/x", expires_at: "2026-11-20T00:00:00Z", emailed: false };
    mount(["manage_machines"]);
    await screen.findByText("Laser session");
    fireEvent.click(screen.getByRole("button", { name: "Actions for Laser session" }));
    expect(screen.queryByRole("menuitem", { name: "Send reminder" })).toBeNull();
    fireEvent.click(screen.getByRole("menuitem", { name: "Pay link" }));
    fireEvent.click(screen.getByRole("button", { name: "Create link" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments/61/area-pay-link", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("https://pay.example/x")).toBeVisible();
  });

  it("lets the area manager record a cash refund on their own offline-paid charge (242 c)", async () => {
    rows = [row({ status: "paid_offline" })];
    mount(["manage_machines"], { entry: "/?status=paid_offline" });
    await screen.findByText("Laser session");
    fireEvent.click(screen.getByRole("button", { name: "Actions for Laser session" }));
    expect(screen.getByRole("menuitem", { name: "Refund" })).toBeVisible();
  });

  it("confirms and rejects 'I paid' claims when claims are on", async () => {
    postResult = (path: string) => ({ ...claim, status: path.endsWith("/reject") ? "rejected" : "confirmed" });
    mount(["manage_machines"], { features: ["billing.offline_claims"], entry: "/?view=claims" });
    expect(await screen.findByText("People who say they paid")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Confirm payment" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments/area-queue/claims/8/confirm", { method: "POST" }));
    expect(await screen.findByText(/Payment confirmed/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Not received" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Nothing arrived" } });
    fireEvent.click(screen.getByRole("button", { name: "Mark not received" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments/area-queue/claims/8/reject",
      { method: "POST", body: JSON.stringify({ note: "Nothing arrived" }) }));
  });

  it("hides the claims tab while offline claims are off", async () => {
    mount(["manage_machines"]);
    await screen.findByText("Laser session");
    expect(screen.queryByRole("link", { name: "Say they paid" })).toBeNull();
  });

  it("pins an area console's queue to its own area", async () => {
    mount(["manage_machines", "edit_inventory", "return_request"], { area: "lending" });
    await screen.findByText("Laser session");
    expect(gets().filter(path => path.includes("area-queue?")).every(path => path.includes("area=lending"))).toBe(true);
    expect(screen.queryByRole("button", { name: /Machines:/ })).toBeNull();
    expect(screen.getByText(/Inventory charges owed to Lab/)).toBeVisible();
  });

  it("shows an error with a retry when the queue fails", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path.includes("summary")) return { groups: [] };
      throw new Error("boom");
    });
    mount(["manage_bookings"]);
    expect(await screen.findByText("Couldn't load payments. Try again.")).toBeVisible();
  });

  it("says when nothing is waiting", async () => {
    rows = [];
    staffRequest.mockImplementation(async (path: string) => path.includes("summary") ? { groups: [] }
      : { count: 0, next: null, previous: null, results: [] });
    mount(["manage_bookings"]);
    expect(await screen.findByText("Nothing to collect. Every charge here is paid or waived.")).toBeVisible();
  });
});

describe("Space Manager's combined view (decision 241/242)", () => {
  const finance = ["view_finance", "record_payment", "manage_makerspace", "manage_machines"];

  it("keeps the whole ledger and groups money by area above it", async () => {
    mount(finance);
    await screen.findByText("Laser session");
    expect(gets().some(path => path.startsWith("/admin/makerspace/7/payments?status=pending"))).toBe(true);
    expect(screen.getByRole("button", { name: "Machines: 2 to collect" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Billing documents" })).toBeVisible();
  });

  it("filters to one area through the area queue when a group is chosen", async () => {
    mount(finance);
    await screen.findByText("Laser session");
    fireEvent.click(screen.getByRole("button", { name: "Inventory: 1 to collect" }));
    await waitFor(() => expect(gets().some(path => path.startsWith("/admin/makerspace/7/payments/area-queue?area=lending"))).toBe(true));
    expect(screen.getByRole("button", { name: "Inventory: 1 to collect" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("decision 259: All tab, area-pinned claims, ?payment= and the handover desk", () => {
  it("offers an All tab that reads the area queue with status=all", async () => {
    mount(["manage_machines"], { entry: "/?status=" });
    await screen.findByText("Laser session");
    expect(screen.getByRole("link", { name: /^All/ })).toBeVisible();
    await waitFor(() => expect(gets().some(path => path.includes("area-queue?") && path.includes("status=all"))).toBe(true));
  });

  it("pins the claims list to the area console it is opened from", async () => {
    mount(["manage_machines"], { features: ["billing.offline_claims"], area: "machines", entry: "/?pay_view=claims" });
    await waitFor(() => expect(gets().some(path => path.includes("area-queue/claims?area=machines"))).toBe(true));
  });

  it("opens one charge from ?payment=<id> whatever its status", async () => {
    rows = [row({ id: 61 }), row({ id: 62, subject_label: "Other session", status: "paid_offline" })];
    mount(["manage_machines"], { entry: "/?payment=62" });
    await screen.findByText("Other session");
    expect(screen.queryByText("Laser session")).not.toBeInTheDocument();
    expect(gets().some(path => path.includes("status=all"))).toBe(true);
  });

  it("gives the handover desk the area queue for loan charges, not the recording ledger", async () => {
    rows = [row({ id: 70, subject_type: "loan_late_fee", subject_label: "Late fee", area: "lending" })];
    mount(["issue_request", "return_request", "view_inventory"]);
    await screen.findByText("Late fee");
    expect(gets().some(path => path.startsWith("/admin/makerspace/7/payments/area-queue"))).toBe(true);
    expect(screen.queryByRole("button", { name: "Billing documents" })).not.toBeInTheDocument();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DonationsArea } from "./DonationsArea";
import { getStaffAccess } from "../staffAccess";
import type { RefundCase } from "../refunds/refundsApi";

const { campaigns, staffRequest } = vi.hoisted(() => ({ campaigns: vi.fn(), staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});
vi.mock("./staffDonationsApi", async () => {
  const actual = await vi.importActual<typeof import("./staffDonationsApi")>("./staffDonationsApi");
  return { ...actual, donationStaffApi: { ...actual.donationStaffApi, campaigns } };
});

beforeEach(() => { campaigns.mockReset().mockResolvedValue([]); staffRequest.mockReset(); });
afterEach(() => document.documentElement.removeAttribute("data-theme"));

function area(features: string[], actions = ["manage_donations"], path = "/admin/donations") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter initialEntries={[path]}><QueryClientProvider client={queryClient}>
    <DonationsArea makerspace={{ id: 2, enabled_modules: [], enabled_features: features }} actions={actions} />
  </QueryClientProvider></MemoryRouter>);
}

describe("decision 550: role-scoped Fundraising area", () => {
  it.each(["light", "dark"])("keeps receipt operations and hides settings in %s theme", async theme => {
    document.documentElement.setAttribute("data-theme", theme);
    area(["finance.donations", "finance.sponsors", "finance.recurring_donations"]);
    expect(screen.getByRole("heading", { name: "Fundraising" })).toHaveClass("title-page");
    for (const name of ["Overview", "Gifts", "Campaigns", "Pledges", "Donors", "Sponsors", "Refunds"]) {
      expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    }
    expect(screen.queryByRole("tab", { name: "Non-profit and receipts" })).not.toBeInTheDocument();
    await waitFor(() => expect(campaigns).toHaveBeenCalledWith(2));
  });

  it("does not fetch or mount donor or sponsor screens with the master off", () => {
    area(["finance.sponsors"], ["manage_donations"], "/admin/donations/sponsors");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.getByText(/Donations are switched off/)).toHaveClass("bg-panel", "text-muted");
    expect(campaigns).not.toHaveBeenCalled();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("keeps the refund subroute dormant when the master is off", () => {
    area([], ["manage_donations"], "/admin/donations/refunds");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("keeps the non-profit settings section for the Space Manager", async () => {
    area(["finance.donations"], ["manage_makerspace", "manage_donations"]);
    expect(screen.getByRole("tab", { name: "Non-profit and receipts" })).toBeInTheDocument();
    await waitFor(() => expect(campaigns).toHaveBeenCalledWith(2));
  });
});

describe("standalone Fundraising money journeys", () => {
  it.each(["light", "dark"])("settles a sponsor charge inside Fundraising with a permanent receipt (%s)", async theme => {
    document.documentElement.setAttribute("data-theme", theme);
    let settled = false;
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/admin/makerspace/2/sponsors") return [{ id: 7, name: "Roof sponsor", tier_name: "",
        logo_url: "", show_on_wall: false, perks_open: 0, archived_at: null }];
      if (path === "/admin/makerspace/2/sponsors/7/charges") return [{ id: 8, sponsor: 7, amount: "25.00",
        currency: "usd", description: "Roof fund", payment_id: 91, payment_status: settled ? "paid_offline" : "pending" }];
      if (path === "/admin/makerspace/2/payments/91/mark-offline" && init?.method === "POST") {
        settled = true;
        return { id: 91, status: "paid_offline" };
      }
      if (path.includes("events")) return { count: 0, results: [] };
      return [];
    });
    expect(getStaffAccess(["manage_donations"], false, false).allowedTabs).toEqual(["donations"]);
    area(["finance.donations", "finance.sponsors"]);
    fireEvent.click(screen.getByRole("tab", { name: "Sponsors" }));
    fireEvent.click(await screen.findByRole("button", { name: /Roof sponsor/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Record payment" }));
    fireEvent.change(screen.getByLabelText("Received"), { target: { value: "" } });
    expect(screen.getByRole("button", { name: "Save receipt" })).toBeDisabled();
    expect(staffRequest.mock.calls.filter(([path]) => path.endsWith("/mark-offline"))).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Method"), { target: { value: "bank_transfer" } });
    fireEvent.change(screen.getByLabelText("Reference"), { target: { value: "ROOF-RECEIPT" } });
    fireEvent.change(screen.getByLabelText("Received"), { target: { value: "2026-11-14T10:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/payments/91/mark-offline",
      { method: "POST", body: JSON.stringify({ settlement: { method: "bank_transfer", reference: "ROOF-RECEIPT",
        received_at: new Date("2026-11-14T10:30").toISOString() } }) }));
    expect(await screen.findByText("Paid offline")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Record payment" })).not.toBeInTheDocument();
    expect(staffRequest.mock.calls.some(([path]) => /\/payments(?:\?|$)/.test(path))).toBe(false);
    expect(screen.queryByText("Membership dues")).not.toBeInTheDocument();
  });

  it.each([
    ["donation", "approve"], ["donation", "decline"],
    ["sponsorship", "approve"], ["sponsorship", "decline"],
  ] as const)("lists only fundraising money and decides a %s case: %s", async (kind, decision) => {
    const row: RefundCase = { id: 12, kind: "due", area: "donations", reason_code: "donation_returned",
      member_reason: "", due_amount: "25.00", policy_snapshot: { rule: "no_policy_area" }, status: "open",
      approved_amount: null, decision_note: "", refund: null, refundable_balance: "25.00", needs_finance_approval: false,
      created_at: "2026-11-14T10:00:00Z", decided_at: null,
      payment: { id: 91, subject_type: kind, subject_label: "Roof gift", status: "paid_offline", amount: "25.00",
        currency: "usd", member_name: "Giver" } };
    const unrelated: RefundCase = { ...row, id: 99, area: "membership", payment: { ...row.payment,
      id: 98, subject_type: "makerspace_membership", subject_label: "Membership dues" } };
    let decided = false;
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => {
      if (init?.method === "POST") { decided = true; return { ...row, status: decision === "approve" ? "approved" : "declined" }; }
      return { count: decided ? 0 : 2, next: null, previous: null, results: decided ? [] : [row, unrelated] };
    });
    area(["finance.donations", "finance.sponsors"]);
    fireEvent.click(screen.getByRole("tab", { name: "Refunds" }));
    const open = await screen.findByRole("button", { name: /Giver.*Roof gift/ });
    const listing = staffRequest.mock.calls.find(([path]) => path.includes("/refund-cases?"))![0];
    expect(new URLSearchParams(listing.split("?")[1]).get("area")).toBe("donations");
    expect(new URLSearchParams(listing.split("?")[1]).get("status")).toBe("open");
    expect(screen.queryByText(/Membership dues/)).not.toBeInTheDocument();
    expect(staffRequest.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    fireEvent.click(open);
    if (decision === "approve") {
      fireEvent.change(screen.getByLabelText("Refund reference (optional)"), { target: { value: "RETURN-SLIP" } });
      fireEvent.click(screen.getByRole("button", { name: /Record.*25\.00 returned/ }));
      await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/refund-cases/12/approve",
        expect.objectContaining({ method: "POST" })));
      const request = staffRequest.mock.calls.find(([path]) => path.endsWith("/approve"))!;
      expect(JSON.parse(request[1].body)).toEqual({ amount: "25.00", note: "",
        receipt: { method: "cash", reference: "RETURN-SLIP", refunded_at: expect.any(String) } });
    } else {
      fireEvent.click(screen.getByRole("radio", { name: "Decline" }));
      fireEvent.click(screen.getByRole("button", { name: "Decline refund" }));
      expect(screen.getByRole("alert")).toHaveTextContent(/They will see this note/);
      expect(staffRequest.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
      fireEvent.change(screen.getByLabelText("Note to the member"), { target: { value: "Already returned" } });
      fireEvent.click(screen.getByRole("button", { name: "Decline refund" }));
      await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/refund-cases/12/decline",
        { method: "POST", body: JSON.stringify({ note: "Already returned" }) }));
    }
    await waitFor(() => expect(screen.queryByRole("button", { name: /Giver.*Roof gift/ })).not.toBeInTheDocument());
    expect(staffRequest.mock.calls.filter(([path]) => path.includes("/refund-cases?"))).toHaveLength(2);
    expect(staffRequest.mock.calls.some(([path]) => /\/99\/(approve|decline)$/.test(path))).toBe(false);
  });
});

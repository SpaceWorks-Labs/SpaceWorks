import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FinancePanel } from "../../finance/FinancePanel";
import { DonationsArea } from "./DonationsArea";
import { GiftsList } from "./GiftsList";
import { SponsorsSection } from "./SponsorsSection";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest,
}));

function wrap(node: ReactNode, path = "/admin/donations") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  // Both areas keep their section in the URL path (0.12.0 row 15), so they need a router.
  return render(<MemoryRouter initialEntries={[path]}><QueryClientProvider client={client}>{node}</QueryClientProvider></MemoryRouter>);
}
const gift = { id: 9, campaign: null, campaign_name: "", pledge: null, period_start: null, donor: null, is_guest: true,
  donor_name: "Grace", donor_email: "g@example.test", donor_note: "", amount: "500.00", currency: "inr", source: "online",
  status: "paid", wants_tax_receipt: true, donor_pan_masked: "••••••234F", donor_address: "1 Main St", tax_receipt_number: "80G-1-000009",
  payment_id: 3, payment_status: "paid_offline", created_at: "2026-11-01T00:00:00Z", paid_at: "2026-11-01T00:00:00Z", cancelled_at: null };
const pending = { ...gift, id: 10, status: "pending", payment_id: 4, payment_status: "pending", tax_receipt_number: "", paid_at: null };
const campaign = { id: 4, kind: "campaign", name: "New laser", slug: "laser", description: "", goal_amount: "1000.00",
  raised_amount: "250.00", currency: "inr", starts_at: null, ends_at: null, is_active: true, is_public: true };
let gifts: unknown[] = [gift];

beforeEach(() => {
  gifts = [gift];
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string) => Promise.resolve(path.includes("/campaigns") ? [campaign]
    : path.includes("/tiers") || path.includes("/perks") || path.includes("/sponsors") ? []
      : path.includes("/donors") ? [{ key: "guest:0", name: "Grace", email: "g@example.test", is_guest: true, gift_count: 1,
        totals: { inr: "500.00" }, last_gift_at: "2026-11-01T00:00:00Z", recurring: false, recognize_publicly: true }]
        : path.includes("/donations") ? gifts : {}));
});

const space = (features: string[]) => ({ id: 2, name: "Lab", enabled_modules: [], enabled_features: features });

describe("Donations area (decision 242 m)", () => {
  it("is one area with its own tabs; Finance no longer carries donations or sponsors", async () => {
    wrap(<DonationsArea makerspace={space(["finance.donations", "finance.sponsors", "finance.recurring_donations"])}
      actions={["manage_donations"]} />);
    const sections = within(screen.getByRole("tablist", { name: "Donation sections" }));
    for (const name of ["Overview", "Gifts", "Campaigns", "Pledges", "Donors", "Sponsors", "Non-profit and receipts"]) {
      expect(sections.getByRole("tab", { name })).toBeInTheDocument();
    }
    expect(await screen.findByText(/₹250.00 of ₹1,000.00/)).toBeInTheDocument();
    wrap(<FinancePanel makerspace={space(["finance.donations", "finance.sponsors"])} canViewFinance canRecordPayment />, "/admin/finance");
    expect(screen.queryByRole("tab", { name: "Donations" })).not.toBeInTheDocument();
  });

  it("hides donation sections while the switch is off", () => {
    wrap(<DonationsArea makerspace={space(["finance.sponsors"])} actions={["manage_donations"]} />);
    expect(screen.queryByRole("tab", { name: "Gifts" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("tab", { name: "Sponsors" }).length).toBeGreaterThan(0);
  });

  it("lists donors without tax identity", async () => {
    wrap(<DonationsArea makerspace={space(["finance.donations"])} actions={["manage_donations"]} />, "/admin/donations/donors");
    expect(await screen.findByText("Grace")).toBeInTheDocument();
    expect(screen.getByText(/Named publicly/)).toBeInTheDocument();
    expect(screen.queryByText(/PAN/)).not.toBeInTheDocument();
  });
});

describe("GiftsList", () => {
  it("lists gifts with the masked PAN only and offers a return case on a received gift", async () => {
    wrap(<GiftsList makerspaceId={2} campaigns={[]} canRecord taxOn />);
    expect(await screen.findByText(/INR 500.00 · Grace/)).toBeInTheDocument();
    expect(screen.getByText(/PAN ••••••234F/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Return…" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Why return it?" }), { target: { value: "Giver asked" } });
    fireEvent.click(screen.getByRole("button", { name: "Open refund case" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/donations/9/return",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ reason: "Giver asked" }) })));
  });

  it("sends a received gift's receipt again", async () => {
    wrap(<GiftsList makerspaceId={2} campaigns={[]} canRecord taxOn />);
    fireEvent.click(await screen.findByRole("button", { name: "Send receipt again" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/donations/9/receipt/reissue",
      expect.objectContaining({ method: "POST" })));
  });

  it("marks a waiting gift received through the ordinary offline settlement", async () => {
    gifts = [pending];
    wrap(<GiftsList makerspaceId={2} campaigns={[]} canRecord taxOn={false} />);
    fireEvent.click(await screen.findByRole("button", { name: "Mark received" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Reference (optional)" }), { target: { value: "UTR1" } });
    fireEvent.click(screen.getByRole("button", { name: "Record as received" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/payments/4/mark-offline",
      expect.objectContaining({ method: "POST" })));
    const [, init] = staffRequest.mock.calls.find(([path]) => String(path).endsWith("/mark-offline"))!;
    expect(JSON.parse(init.body).settlement).toMatchObject({ method: "cash", reference: "UTR1" });
  });

  it("decides a giver's paid claim on the gift itself", async () => {
    gifts = [{ ...pending, open_claim: { id: 7, reference: "UTR9", paid_on: "2026-11-02", status: "submitted" } }];
    wrap(<GiftsList makerspaceId={2} campaigns={[]} canRecord taxOn={false} />);
    expect(await screen.findByText(/reference UTR9/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm payment" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/donations/10/claim/confirm",
      expect.objectContaining({ method: "POST" })));
  });

  it("is read-only without donations authority", async () => {
    wrap(<GiftsList makerspaceId={2} campaigns={[]} canRecord={false} taxOn={false} />);
    await screen.findByText(/INR 500.00 · Grace/);
    expect(screen.queryByRole("button", { name: "Record a gift" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Return…" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeInTheDocument();
  });
});

describe("SponsorsSection", () => {
  it("shows the empty state and lets finance staff add a sponsor", async () => {
    wrap(<SponsorsSection makerspaceId={2} canRecordPayment />);
    expect(await screen.findByText("No sponsors yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add a sponsor" }));
    expect(await screen.findByRole("dialog", { name: "Add a sponsor" })).toBeInTheDocument();
  });
});

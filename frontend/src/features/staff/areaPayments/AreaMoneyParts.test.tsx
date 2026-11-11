import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OverflowMenu } from "../../../components/ui";
import { StaffListContext } from "../StaffListContext";
import { HandoverQueueHome } from "../panels/DashboardAnalyticsWidgets";
import type { PricingDefault } from "../pricing/pricingApi";
import { AreaPricingSection } from "./AreaPricingSection";
import { ChargeSettle } from "./ChargeSettle";
import { useAreaPaymentsDrawer } from "./useAreaPaymentsDrawer";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const card = (extra: Partial<PricingDefault> = {}): PricingDefault => ({
  domain: "bookings", label: "Bookings", enabled: true, currency: "usd", mode: "paid", stored: true, editable: false,
  via: null, locked: false, refusal: "setting_not_delegated", rental_timing: null, rental_timing_editable: false,
  failed_job_charge: null, lending: null, lines: [{ component: "per_hour", label: "Per hour", unit: "hour", has_cap: false,
    has_grace: false, has_increment: false, has_minimum: false, discountable: true, staff_set: false, prefill_only: false,
    read_only: false, amount: "10.00", cap: null, grace_units: 0, billing_increment: 0, minimum: 0, source: "default" }], ...extra,
} as PricingDefault);
let pricing = card();
beforeEach(() => {
  pricing = card();
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    if (options?.method === "POST") return { id: 5, status: "paid_offline" };
    if (path.includes("/pricing/")) return pricing;
    if (path.includes("summary")) return { groups: [] };
    return { count: 0, next: null, previous: null, results: [] };
  });
});

function wrap(node: ReactNode, actions: string[], features: string[] = [], modules: string[] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "x", canShare: false, actions, makerspace: { id: 3, enabled_modules: modules, enabled_features: features } }}>
      {node}
    </StaffListContext.Provider></QueryClientProvider></MemoryRouter>);
}

describe("ChargeSettle (decision 242 a: settle where the record is shown)", () => {
  const charge = { id: 5, status: "pending", amount: "4.00", currency: "usd", subject_type: "loan_late_fee" };

  it("offers Mark offline and Waive to the charge's owner and posts the receipt", async () => {
    wrap(<ChargeSettle charge={charge} />, ["return_request"]);
    expect(screen.getByRole("button", { name: "Payment actions" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Mark offline" }));
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/payments/5/mark-offline", expect.objectContaining({ method: "POST" })));
  });

  it("lets a record_payment holder record cash but not waive another area's debt", () => {
    wrap(<ChargeSettle charge={charge} />, ["record_payment"]);
    expect(screen.getByRole("button", { name: "Mark offline" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Payment actions" })).toBeNull();
  });

  it("shows nothing without authority, or once the charge is settled", () => {
    const { container } = wrap(<><ChargeSettle charge={charge} /><ChargeSettle charge={{ ...charge, status: "paid_offline" }} /></>, ["manage_events"]);
    expect(container.textContent).toBe("");
  });

  it("scopes session charges to the machine area", () => {
    wrap(<ChargeSettle charge={{ ...charge, subject_type: "machine_session" }} />, ["manage_machines"]);
    expect(screen.getByRole("button", { name: "Mark offline" })).toBeVisible();
  });
});

describe("AreaPricingSection (decision 242 d)", () => {
  it("shows Charging on and the read-only rate card when pricing is not delegated", async () => {
    wrap(<AreaPricingSection makerspaceId={3} domain="bookings" />, ["manage_bookings"],
      ["charges.enabled", "charges.bookings", "charges.pricing"], ["bookings"]);
    expect(screen.getByText("On")).toBeVisible();
    expect(screen.getByText("(Space Manager setting)")).toBeVisible();
    expect(await screen.findByText(/You can see these prices but not change them/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /Save/ })).toBeNull();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/pricing/bookings");
  });

  it("lets a manager the Space Manager delegated to edit the card", async () => {
    pricing = card({ editable: true, refusal: null, via: "delegated" });
    wrap(<AreaPricingSection makerspaceId={3} domain="bookings" />, ["manage_bookings"],
      ["charges.enabled", "charges.bookings", "charges.pricing"], ["bookings"]);
    expect(await screen.findByRole("radio", { name: "Paid" })).toBeEnabled();
  });

  it("says Charging off and needs no rate card when price lists are off", () => {
    wrap(<AreaPricingSection makerspaceId={3} domain="inventory" />, ["edit_inventory"], ["charges.enabled"]);
    expect(screen.getByText("Off")).toBeVisible();
    expect(screen.getByText(/Price lists are off in this space/)).toBeVisible();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("points the shop at per-item prices", () => {
    wrap(<AreaPricingSection makerspaceId={3} domain="shop" />, ["manage_shop"], ["charges.enabled", "charges.shop", "charges.pricing"], ["shop"]);
    expect(screen.getByText(/Each shop item has its own price/)).toBeVisible();
  });
});

function DrawerHost({ area }: { area: "events" | "machines" }) {
  const drawer = useAreaPaymentsDrawer(3, area);
  return <><OverflowMenu label="More" actions={drawer.actions} />{drawer.dialog}</>;
}

describe("useAreaPaymentsDrawer (decision 242 a: the queue inside each area console)", () => {
  it("opens the area's own queue pinned to that area", async () => {
    wrap(<DrawerHost area="events" />, ["manage_events"]);
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Payments" }));
    expect((await screen.findAllByText("Events payments"))[0]).toBeVisible();
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("area-queue?area=events"))).toBe(true));
  });

  it("offers no entry to someone who owns no charge in that area", () => {
    wrap(<DrawerHost area="machines" />, ["manage_events"]);
    // An empty action list renders no menu at all.
    expect(screen.queryByRole("button", { name: "More" })).toBeNull();
    expect(screen.queryByRole("menuitem", { name: "Payments" })).toBeNull();
  });
});

describe("HandoverQueueHome (audit IN11)", () => {
  it("splits due today from overdue and links pending charges for a desk that records cash", () => {
    render(<MemoryRouter><HandoverQueueHome slug="lab" queues={{ ready_to_issue: 1, due_returns: 2, pickups: 0, due_today: 3, overdue: 2, to_record: 4 }} /></MemoryRouter>);
    expect(screen.getByText("Due back today")).toBeVisible();
    expect(screen.getByText("Overdue")).toBeVisible();
    expect(screen.getByText("Payments to record")).toBeVisible();
    expect(screen.queryByText("Due returns")).toBeNull();
    expect(screen.getByRole("link", { name: /Payments to record/ }).getAttribute("href")).toContain("payments?status=pending");
  });

  it("hides the record tile when the desk has nothing to record (no record_payment)", () => {
    render(<MemoryRouter><HandoverQueueHome slug="lab" queues={{ ready_to_issue: 0, due_returns: 0, pickups: 0, due_today: 0, overdue: 0, to_record: 0 }} /></MemoryRouter>);
    expect(screen.queryByText("Payments to record")).toBeNull();
  });
});

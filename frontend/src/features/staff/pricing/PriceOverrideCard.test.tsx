import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import type { PriceOverrideCard as Card } from "./priceOverrideApi";
import { PriceOverrideCard } from "./PriceOverrideCard";
import { EventPriceNote, PlanPriceNote } from "./PricingNote";

vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn() }));

const card = (overrides: Partial<Card> = {}): Card => ({
  target_type: "inventory_product", target_id: 7, label: "Drill", domain: "loans", currency: "inr", editable: true, enabled: true,
  components: [
    { component: "deposit", label: "Refundable deposit", unit: "item", has_cap: false, mode: "inherit", amount: null, cap: null,
      effective_amount: "200.00", effective_source: "default", default_amount: "200.00" },
    { component: "late_per_day", label: "Late fee per day", unit: "day", has_cap: true, mode: "free", amount: null, cap: null,
      effective_amount: "0.00", effective_source: "override_free", default_amount: "10.00" },
  ],
  ...overrides,
});

function client(spaces?: unknown) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (spaces !== undefined) queryClient.setQueryData(["staff", "makerspaces"], spaces);
  return queryClient;
}

function show(node: ReactNode, queryClient = client()) {
  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

const notFound = async () => { throw Object.assign(new Error("Price lists are off."), { status: 404, code: "pricing_disabled" }); };

describe("PriceOverrideCard", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

  it("shows each component's mode and its effective price in words", async () => {
    vi.mocked(staffRequest).mockResolvedValue(card());
    show(<PriceOverrideCard makerspaceId={3} targetType="inventory_product" targetId={7} />);
    expect(await screen.findByText("Effective: INR 200.00 (space default)")).toBeVisible();
    expect(screen.getByText("Effective: INR 0.00 (free for this item)")).toBeVisible();
    expect(screen.getByRole("radiogroup", { name: "Refundable deposit price" })).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/pricing/overrides/inventory_product/7");
  });

  it("saves a custom amount with PUT and shows the server's answer", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce(card());
    const saved = card();
    saved.components[0] = { ...saved.components[0], mode: "custom", amount: "350.00", effective_amount: "350.00", effective_source: "item" };
    vi.mocked(staffRequest).mockResolvedValueOnce(saved);
    show(<PriceOverrideCard makerspaceId={3} targetType="inventory_product" targetId={7} />);
    const group = await screen.findByRole("radiogroup", { name: "Refundable deposit price" });
    fireEvent.click(group.querySelector('[role="radio"]:last-child')!);
    fireEvent.change(screen.getByLabelText("Custom amount (INR)"), { target: { value: "350" } });
    fireEvent.click(screen.getByRole("button", { name: "Save refundable deposit" }));
    await waitFor(() => expect(staffRequest).toHaveBeenLastCalledWith("/admin/makerspace/3/pricing/overrides/inventory_product/7",
      { method: "PUT", body: JSON.stringify({ component: "deposit", mode: "custom", amount: "350" }) }));
    expect(await screen.findByText("Effective: INR 350.00 (this item's own price)")).toBeVisible();
    expect(screen.getByText("Price saved.")).toBeInTheDocument();
  });

  it("sends a cap for a capped component and clears with inherit", async () => {
    vi.mocked(staffRequest).mockResolvedValue(card());
    show(<PriceOverrideCard makerspaceId={3} targetType="inventory_product" targetId={7} />);
    const group = await screen.findByRole("radiogroup", { name: "Late fee per day price" });
    fireEvent.click(group.querySelector('[role="radio"]')!);
    fireEvent.click(screen.getByRole("button", { name: "Save late fee per day" }));
    await waitFor(() => expect(staffRequest).toHaveBeenLastCalledWith(expect.any(String),
      { method: "PUT", body: JSON.stringify({ component: "late_per_day", mode: "inherit" }) }));
  });

  it("is read-only when the account may not edit the item", async () => {
    vi.mocked(staffRequest).mockResolvedValue(card({ editable: false }));
    show(<PriceOverrideCard makerspaceId={3} targetType="machine" targetId={7} />);
    expect(await screen.findByText("Prices are set by staff who edit this item.")).toBeVisible();
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("renders nothing on 404 and does not ask while price lists are off", async () => {
    vi.mocked(staffRequest).mockImplementation(notFound);
    const { container } = show(<PriceOverrideCard makerspaceId={3} targetType="bookable_space" targetId={7} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(container).toBeEmptyDOMElement();
    vi.mocked(staffRequest).mockClear();
    const off = show(<PriceOverrideCard makerspaceId={3} targetType="bookable_space" targetId={8} />,
      client([{ id: 3, enabled_modules: [], enabled_features: [] }]));
    expect(off.container).toBeEmptyDOMElement();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("folds into a disclosure when compact", async () => {
    vi.mocked(staffRequest).mockResolvedValue(card({ target_type: "consumable_pool" }));
    show(<PriceOverrideCard makerspaceId={3} targetType="consumable_pool" targetId={7} compact />);
    expect(await screen.findByText("Price", { selector: "summary" })).toBeVisible();
  });
});

describe("pricing notes", () => {
  it("show only where price lists are on", () => {
    // #184 G5 (0acf6df0): a note also needs its domain's charges tracked (events, membership).
    const on = client([{ id: 3, enabled_modules: ["events", "membership"],
      enabled_features: ["charges.pricing", "charges.enabled", "charges.events", "charges.membership"] }]);
    show(<><EventPriceNote /><PlanPriceNote makerspaceId={3} /></>, on);
    expect(screen.getByText(/only prefills new events/)).toBeVisible();
    expect(screen.getByText(/member discounts are in Settings > Pricing/)).toBeVisible();
  });

  it("stay hidden when off or unknown", () => {
    const { container } = show(<><EventPriceNote /><PlanPriceNote makerspaceId={3} /></>,
      client([{ id: 3, enabled_modules: [], enabled_features: [] }]));
    expect(container).toBeEmptyDOMElement();
    const unknown = show(<PlanPriceNote makerspaceId={3} />);
    expect(unknown.container).toBeEmptyDOMElement();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EventMerchLink, EventShopOfferList } from "./EventShopOffers";
import { eventOffersEnabled, type EventShopOffers } from "./eventOffersApi";
import { rememberedPickupEvent } from "./pickupPreference";
import type { ShopPublicProduct } from "./shopApi";

const mocks = vi.hoisted(() => ({ tenant: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  tenantPublicRequest: mocks.tenant }));

const tee = { id: 5, slug: "tee", name: "Fair tee", kind: "merch", category: "", unit: "each", image_url: "", price_from: 20, price_to: 20,
  members_only: false, max_per_order: null, sold_out: false, variants: [{ id: 11, name: "M", options: {}, price: 20, sold_out: false,
    stock_label: null, stock_count: null }] } as unknown as ShopPublicProduct;
const offers: EventShopOffers = { event: { id: 41, title: "Maker Fair", starts_at: "2026-12-01T10:00:00Z" }, currency: "inr", products: [tee] };
const on = { modules: ["shop", "events"], features: ["shop.online", "shop.event_pickup"] };
const path = (part = "") => `/m/lab/${part}`;

function wrap(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); window.localStorage.clear(); });

describe("event merch (#135 Q-S18)", () => {
  it("needs the shop online, event pickup and Events", () => {
    expect(eventOffersEnabled(on)).toBe(true);
    expect(eventOffersEnabled({ ...on, modules: ["shop"] })).toBe(false);
    expect(eventOffersEnabled({ ...on, modules: ["events"] })).toBe(false);
    expect(eventOffersEnabled({ ...on, features: ["shop.online"] })).toBe(false);
    expect(eventOffersEnabled(null)).toBe(false);
  });

  it("links each item into the normal shop with this event as the pickup and remembers it", () => {
    wrap(<EventShopOfferList offers={offers} slug="lab" path={path} selling />);
    const link = screen.getByRole("link", { name: "Fair tee" });
    expect(link).toHaveAttribute("href", "/m/lab/shop/tee?pickup_event=41");
    expect(screen.getByText(/paid separately from registration/)).toBeVisible();
    fireEvent.click(link);
    expect(rememberedPickupEvent("lab")).toEqual(offers.event);
  });

  it("hides prices while shop charges are off", () => {
    wrap(<EventShopOfferList offers={offers} slug="lab" path={path} selling={false} />);
    expect(screen.queryByText(/20/)).toBeNull();
  });

  it("shows the ticket-page link only when the event offers something", async () => {
    mocks.tenant.mockResolvedValue(offers);
    wrap(<EventMerchLink slug="lab" publicToken="tok" bootstrap={on} path={path} />);
    const link = await screen.findByRole("link", { name: "Add merch for pickup at this event" });
    expect(link).toHaveAttribute("href", "/m/lab/shop?pickup_event=41");
    expect(mocks.tenant).toHaveBeenCalledWith("lab", "/public/m/lab/shop/events/tok/offers/");
  });

  it("never asks the server when the shop or Events is off", () => {
    wrap(<EventMerchLink slug="lab" publicToken="tok" bootstrap={{ ...on, modules: ["events"] }} path={path} />);
    expect(mocks.tenant).not.toHaveBeenCalled();
    expect(screen.queryByRole("link")).toBeNull();
  });
});

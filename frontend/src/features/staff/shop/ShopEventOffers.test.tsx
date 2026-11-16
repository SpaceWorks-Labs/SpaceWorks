import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShopEventOffers } from "./ShopEventOffers";
import { shopAccess, shopViews } from "./shopAccess";

const mocks = vi.hoisted(() => ({ staff: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  staffRequest: mocks.staff }));

const events = [{ id: 41, title: "Maker Fair", starts_at: "2026-12-01T10:00:00Z", status: "published", variant_ids: [11] }];
const products = { count: 1, next: null, previous: null, results: [{ id: 5, name: "Fair tee", is_active: true, archived_at: null,
  variants: [{ id: 11, name: "M", is_active: true, archived_at: null }, { id: 12, name: "L", is_active: true, archived_at: null }] }] };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.staff.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(
    init?.method === "PUT" ? JSON.parse(String(init.body)) : path.includes("event-offers") ? events : products));
});

describe("staff event merch (#135 Q-S18)", () => {
  it("is a manager tab only with event pickup and Events on", () => {
    const space = (features: string[], modules: string[]) => ({ enabled_modules: modules, enabled_features: features });
    const keys = (actions: string[], features: string[], modules: string[]) =>
      shopViews(shopAccess(actions, false, space(features, modules))).map(view => view.key);
    expect(keys(["manage_shop"], ["shop.event_pickup"], ["shop", "events"])).toContain("events");
    expect(keys(["manage_shop"], ["shop.event_pickup"], ["shop"])).not.toContain("events");
    expect(keys(["manage_shop"], [], ["shop", "events"])).not.toContain("events");
    expect(keys(["sell_shop"], ["shop.event_pickup"], ["shop", "events"])).not.toContain("events");
  });

  it("saves the chosen items for the event", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><ShopEventOffers makerspaceId={3} /></QueryClientProvider>);
    const medium = await screen.findByRole("checkbox", { name: "Fair tee · M" });
    expect(medium).toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: "Fair tee · L" }));
    fireEvent.click(screen.getByRole("button", { name: "Save event merch" }));
    await waitFor(() => expect(mocks.staff).toHaveBeenCalledWith("/admin/makerspaces/3/shop/event-offers/41/",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ variant_ids: [11, 12] }) })));
    expect(await screen.findByText("Event merch saved.")).toBeVisible();
  });
});

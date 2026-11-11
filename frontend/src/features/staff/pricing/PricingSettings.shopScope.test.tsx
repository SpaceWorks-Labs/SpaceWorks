import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { PricingSettings } from "./PricingSettings";

vi.mock("./PricingDomainCard", () => ({ PricingDomainCard: () => null }));
vi.mock("./PricingCurrency", () => ({ PricingCurrency: () => null }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"),
  staffRequest: async (path: string) => path.endsWith("/currency") ? { default_currency: "usd" } : [] }));

it("offers Shop and item-price discount scope without introducing a Shop rate-card tab", async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <PricingSettings makerspace={{ id: 7, enabled_modules: ["shop"],
      enabled_features: ["charges.enabled", "charges.pricing", "charges.discounts", "charges.shop"] }} canManageMakerspace />
  </QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "New discount" }));
  const shop = screen.getByRole("checkbox", { name: "Shop" });
  fireEvent.click(shop);
  expect(shop).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /Item price/ })).toBeVisible();
  expect(screen.queryByRole("tab", { name: "Shop" })).not.toBeInTheDocument();
});

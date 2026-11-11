import { expect, it } from "vitest";
import { priceRange } from "./shopApi";

it.each([
  [{ price_from: 0, price_to: 0 }, "$0.00"],
  [{ price_from: 0, price_to: 10 }, "$0.00 – $10.00"],
  [{ price_from: 0, price_to: null }, "$0.00"],
  [{ price_from: 10, price_to: 10 }, "$10.00"],
  [{ price_from: 10, price_to: 20 }, "$10.00 – $20.00"],
  [{ price_from: null, price_to: null }, ""],
] as const)("keeps public numeric prices visible while respecting hidden prices: %j", (product, expected) => {
  expect(priceRange(product, "usd")).toBe(expected);
});

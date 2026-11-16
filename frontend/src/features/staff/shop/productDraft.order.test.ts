import { expect, it } from "vitest";
import { draftFromForm, formFromProduct, formProblem } from "./productDraft";
import { shopAccess } from "./shopAccess";
import type { ShopProduct } from "./staffShopApi";

it("preserves stored product and variant display order through an unrelated product edit", () => {
  const product: ShopProduct = { id: 3, name: "Kit", kind: "kit", sort_order: 17, components: [],
    image_url: "", archived_at: null, created_at: "2026-11-07T00:00:00Z", updated_at: "2026-11-07T00:00:00Z",
    variants: [{ id: 7, name: "Standard", price: "5.00", sort_order: 42, options: {},
      on_hand: 0, held: 0, available: 0, archived_at: null }] };
  const form = formFromProduct(product);
  form.name = "Updated kit";
  const draft = draftFromForm(form, shopAccess(["manage_shop"], false, { enabled_modules: ["shop"], enabled_features: [] }));
  expect(draft.sort_order).toBe(17);
  expect(draft.variants?.[0].sort_order).toBe(42);
  expect(draft).not.toHaveProperty("slug");
});

it("keeps the existing zero order default and refuses fractional display positions", () => {
  const form = formFromProduct();
  expect(form.sort_order).toBe(0);
  form.name = "Kit"; form.variants[0].price = "5.00"; form.sort_order = 1.5;
  expect(formProblem(form)).toBe("Display order must be a whole number.");
});

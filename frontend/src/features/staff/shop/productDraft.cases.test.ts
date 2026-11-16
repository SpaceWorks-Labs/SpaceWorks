import { describe, expect, it } from "vitest";
import { draftFromForm, formFromProduct, formProblem, KIND_LABELS, type ProductForm } from "./productDraft";
import { shopAccess } from "./shopAccess";
import type { ShopProduct } from "./staffShopApi";

const ALL = ["shop.tax", "shop.order_limits", "shop.member_prices", "shop.public_stock", "shop.bundles", "shop.consumable_link"];
const full = () => shopAccess(["manage_shop"], false, { enabled_modules: ["shop"], enabled_features: ALL });
const bare = () => shopAccess(["manage_shop"], false, { enabled_modules: ["shop"], enabled_features: [] });
const product = (over: Partial<ShopProduct> = {}): ShopProduct => ({ id: 3, name: "Kit", components: [], image_url: "", archived_at: null,
  created_at: "2026-11-07T00:00:00Z", updated_at: "2026-11-07T00:00:00Z", variants: [], ...over } as ShopProduct);
const valid = (over: Partial<ProductForm> = {}): ProductForm => ({ ...formFromProduct(), name: "Kit", ...over, variants: over.variants ?? [{ ...formFromProduct().variants[0], price: "5.00" }] });

describe("formFromProduct", () => {
  it("starts a new product as public, active merchandise with one blank variant", () => {
    const form = formFromProduct();
    expect(form).toMatchObject({ name: "", kind: "merch", is_public: true, is_active: true, sort_order: 0, max_per_order: "", tax_percent: "", bundle_mode: false, parts: [] });
    expect(form.variants).toHaveLength(1);
  });
  it("fills defaults for every optional field a stored product lacks", () => {
    expect(formFromProduct(product())).toMatchObject({ kind: "other", category: "", unit: "", description: "", is_public: true, is_active: true, sort_order: 0,
      max_per_order: "", members_only: false, show_exact_stock: false, tax_percent: "", hsn_code: "", bundle_mode: false });
  });
  it("copies stored values, converts basis points to a percent and the cap to text", () => {
    const form = formFromProduct(product({ kind: "kit", category: "c", unit: "u", description: "d", is_public: false, is_active: false, sort_order: 4,
      max_per_order: 3, members_only: true, show_exact_stock: true, tax_rate_bps: 1250, hsn_code: "9983", bundle_mode: true }));
    expect(form).toMatchObject({ kind: "kit", category: "c", unit: "u", description: "d", is_public: false, is_active: false, sort_order: 4,
      max_per_order: "3", members_only: true, show_exact_stock: true, tax_percent: "12.5", hsn_code: "9983", bundle_mode: true });
  });
  it("keeps a zero tax rate as '0' rather than blank", () => expect(formFromProduct(product({ tax_rate_bps: 0 })).tax_percent).toBe("0"));
  it("lists live variants only, with stable keys, linked product text and option pairs", () => {
    const form = formFromProduct(product({ variants: [
      { id: 7, name: "S", sku: "K-S", price: "5.00", reorder_point: 2, sort_order: 1, linked_product_id: 9, is_active: false, options: { size: "S" }, on_hand: 4, available: 3, archived_at: null },
      { id: 8, name: "Old", price: "1.00", options: {}, on_hand: 0, held: 0, available: 0, archived_at: "2026-01-01T00:00:00Z" },
      { id: 9, price: "2.00", options: null, on_hand: 0, held: 0, available: 0, archived_at: null },
    ] as ShopProduct["variants"] }));
    expect(form.variants.map(v => v.key)).toEqual(["v7", "v9"]);
    expect(form.variants[0]).toMatchObject({ id: 7, name: "S", sku: "K-S", price: "5.00", reorder_point: 2, sort_order: 1, linked_product_id: "9",
      is_active: false, options: [["size", "S"]], on_hand: 4, available: 3 });
    expect(form.variants[1]).toMatchObject({ name: "", sku: "", reorder_point: 0, sort_order: 0, linked_product_id: "", is_active: true, options: [] });
  });
  it("turns bundle components into numbers, defaulting an unreadable quantity to 1", () => expect(formFromProduct(product({
    components: [{ variant_id: "5", quantity: "2" }, { variant_id: 6, quantity: "x" }] as never })).parts).toEqual([{ variant_id: 5, quantity: 2 }, { variant_id: 6, quantity: 1 }]));
});

describe("draftFromForm", () => {
  it("writes only the switched-on features, so a feature turned off never clears stored values", () => {
    const form = valid({ max_per_order: "4", members_only: true, show_exact_stock: true, tax_percent: "5", hsn_code: "1", bundle_mode: true });
    const draft = draftFromForm(form, bare());
    for (const key of ["max_per_order", "members_only", "show_exact_stock", "tax_rate_bps", "hsn_code", "bundle_mode", "component_input"]) expect(draft).not.toHaveProperty(key);
    expect(draft.variants?.[0]).not.toHaveProperty("linked_product_id");
  });
  it("writes every switched-on feature with trimmed and converted values", () => {
    const form = valid({ name: "  Kit ", category: " c ", unit: " u ", max_per_order: "4", members_only: true, show_exact_stock: true, tax_percent: " 12.5 ", hsn_code: " 99 " });
    const draft = draftFromForm(form, full());
    expect(draft).toMatchObject({ name: "Kit", category: "c", unit: "u", max_per_order: 4, members_only: true, show_exact_stock: true, tax_rate_bps: 1250, hsn_code: "99", bundle_mode: false, component_input: [] });
  });
  it("sends null for a blank cap and a blank tax rate", () => expect(draftFromForm(valid(), full())).toMatchObject({ max_per_order: null, tax_rate_bps: null }));
  it("sends bundle parts only in bundle mode and only those with a variant", () => {
    const parts = [{ variant_id: 5, quantity: 2 }, { variant_id: 0, quantity: 1 }];
    expect(draftFromForm(valid({ bundle_mode: true, parts }), full()).component_input).toEqual([{ variant_id: 5, quantity: 2 }]);
    expect(draftFromForm(valid({ bundle_mode: false, parts }), full()).component_input).toEqual([]);
  });
  it("names a blank variant Standard, trims its fields, drops blank option keys and keeps ids", () => {
    const base = valid().variants[0];
    const draft = draftFromForm(valid({ variants: [{ ...base, id: 7, name: " ", sku: " s ", price: " 5.00 ", options: [[" size ", " L "], ["", "x"]], linked_product_id: "9" },
      { ...base, price: "1.00", sort_order: undefined as never, linked_product_id: "" }] }), full());
    expect(draft.variants?.[0]).toEqual({ id: 7, name: "Standard", options: { size: "L" }, sku: "s", price: "5.00", reorder_point: 0, sort_order: 0, is_active: true, linked_product_id: 9 });
    expect(draft.variants?.[1]).not.toHaveProperty("id");
    expect(draft.variants?.[1]).toMatchObject({ sort_order: 0, linked_product_id: null });
  });
});

describe("formProblem", () => {
  it("accepts a valid product", () => expect(formProblem(valid())).toBe(""));
  it("asks for a name", () => expect(formProblem(valid({ name: "  " }))).toBe("Give the product a name."));
  it("refuses a fractional display order on the product or on a variant", () => {
    expect(formProblem(valid({ sort_order: 2.5 }))).toBe("Display order must be a whole number.");
    expect(formProblem(valid({ variants: [{ ...valid().variants[0], sort_order: 1.5 }] }))).toBe("Display order must be a whole number.");
  });
  it("requires at least one variant", () => expect(formProblem(valid({ variants: [] }))).toBe("Add at least one variant."));
  it.each(["", "abc", "5.123", "-1", "5,00"])("refuses the price %j", (price) => expect(formProblem(valid({ variants: [{ ...valid().variants[0], price }] }))).toBe("Every variant needs a price, like 250 or 99.50."));
  it.each(["250", "99.5", "99.50"])("accepts the price %s", (price) => expect(formProblem(valid({ variants: [{ ...valid().variants[0], price }] }))).toBe(""));
  it.each(["-1", "100.5", "abc"])("refuses the tax rate %s", (tax) => expect(formProblem(valid({ tax_percent: tax }))).toBe("The tax rate is a percent between 0 and 100."));
  it.each(["0", "100", "18"])("accepts the tax rate %s", (tax) => expect(formProblem(valid({ tax_percent: tax }))).toBe(""));
});

describe("KIND_LABELS", () => it("names every kind", () => expect(KIND_LABELS).toEqual({ consumable: "Consumable", kit: "Kit", merch: "Merchandise", other: "Other" })));

import { t } from "@lingui/core/macro";
import { fromPairs, toPairs } from "./ShopOptionsEditor";
import type { ShopAccess } from "./shopAccess";
import type { ProductDraft, ShopProduct } from "./staffShopApi";
import { blankVariant, type VariantRow } from "./ShopVariantsEditor";
import type { BundlePart } from "./ShopBundleParts";

/** The form's local model: strings for typed inputs, tax as a percent, variants with stable React keys. */
export type ProductForm = {
  name: string; kind: ProductDraft["kind"]; category: string; unit: string; description: string; is_public: boolean; is_active: boolean;
  sort_order: number; max_per_order: string; members_only: boolean; show_exact_stock: boolean; tax_percent: string; hsn_code: string; bundle_mode: boolean;
  variants: VariantRow[]; parts: BundlePart[];
};

export const KIND_LABELS: Record<ProductDraft["kind"], string> = { consumable: t`Consumable`, kit: t`Kit`, merch: t`Merchandise`, other: t`Other` };

export function formFromProduct(product?: ShopProduct): ProductForm {
  if (!product) return { name: "", kind: "merch", category: "", unit: "", description: "", is_public: true, is_active: true, sort_order: 0, max_per_order: "",
    members_only: false, show_exact_stock: false, tax_percent: "", hsn_code: "", bundle_mode: false, variants: [blankVariant()], parts: [] };
  return {
    name: product.name, kind: product.kind ?? "other", category: product.category ?? "", unit: product.unit ?? "",
    description: product.description ?? "", is_public: product.is_public ?? true, is_active: product.is_active ?? true,
    sort_order: product.sort_order ?? 0, max_per_order: product.max_per_order ? String(product.max_per_order) : "", members_only: product.members_only ?? false,
    show_exact_stock: product.show_exact_stock ?? false,
    tax_percent: product.tax_rate_bps === null || product.tax_rate_bps === undefined ? "" : String(product.tax_rate_bps / 100),
    hsn_code: product.hsn_code ?? "", bundle_mode: product.bundle_mode ?? false,
    variants: (product.variants ?? []).filter(variant => !variant.archived_at).map(variant => ({
      key: `v${variant.id}`, id: variant.id, name: variant.name ?? "", sku: variant.sku ?? "", price: variant.price,
      reorder_point: variant.reorder_point ?? 0, sort_order: variant.sort_order ?? 0, linked_product_id: variant.linked_product_id ? String(variant.linked_product_id) : "",
      is_active: variant.is_active ?? true, options: toPairs(variant.options), on_hand: variant.on_hand, available: variant.available })),
    parts: product.components.map(part => ({ variant_id: Number(part.variant_id), quantity: Number(part.quantity) || 1 })),
  };
}

/** Only switched-on features are written, so turning a feature off never silently clears its stored values. */
export function draftFromForm(form: ProductForm, access: ShopAccess): Partial<ProductDraft> {
  const { features } = access;
  return {
    name: form.name.trim(), kind: form.kind, category: form.category.trim(), unit: form.unit.trim(), description: form.description,
    is_public: form.is_public, is_active: form.is_active, sort_order: form.sort_order,
    ...(features.orderLimits ? { max_per_order: form.max_per_order ? Number(form.max_per_order) : null } : {}),
    ...(features.memberPrices ? { members_only: form.members_only } : {}),
    ...(features.publicStock ? { show_exact_stock: form.show_exact_stock } : {}),
    ...(features.tax ? { tax_rate_bps: form.tax_percent.trim() ? Math.round(Number(form.tax_percent) * 100) : null, hsn_code: form.hsn_code.trim() } : {}),
    ...(features.bundles ? { bundle_mode: form.bundle_mode, component_input: form.bundle_mode ? form.parts.filter(part => part.variant_id) : [] } : {}),
    variants: form.variants.map(row => ({ ...(row.id !== undefined ? { id: row.id } : {}), name: row.name.trim() || "Standard",
      options: fromPairs(row.options), sku: row.sku.trim(), price: row.price.trim(), reorder_point: row.reorder_point, sort_order: row.sort_order ?? 0, is_active: row.is_active,
      ...(features.consumableLink ? { linked_product_id: row.linked_product_id ? Number(row.linked_product_id) : null } : {}) })),
  };
}

export function formProblem(form: ProductForm) {
  if (!form.name.trim()) return "Give the product a name.";
  if (!Number.isInteger(form.sort_order) || form.variants.some(row => !Number.isInteger(row.sort_order ?? 0))) return t`Display order must be a whole number.`;
  if (!form.variants.length) return "Add at least one variant.";
  if (form.variants.some(row => !/^\d+(\.\d{1,2})?$/.test(row.price.trim()))) return "Every variant needs a price, like 250 or 99.50.";
  if (form.tax_percent.trim() && !(Number(form.tax_percent) >= 0 && Number(form.tax_percent) <= 100)) return "The tax rate is a percent between 0 and 100.";
  return "";
}

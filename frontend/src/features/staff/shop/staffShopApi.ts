import { t } from "@lingui/core/macro";
import type {
  ShopMovement, ShopProduct, ShopSettings, ShopStaffVariant, ShopStockMoveKindEnum,
} from "../../../generated/api";
import { StructuredApiError, staffRequest } from "../../../lib/api";

/** Release 2 L22: the staff catalogue, stock and shop settings. Orders, desk and cash live in staffShopOrdersApi. */
export type { ShopMovement, ShopProduct, ShopSettings, ShopStaffVariant };
export type Paged<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type VariantDraft = { id?: number; name: string; options: Record<string, string>; sku: string; price: string;
  reorder_point: number; linked_product_id?: number | null; is_active: boolean };
export type ProductDraft = Pick<ShopProduct, "name"> & {
  kind: NonNullable<ShopProduct["kind"]>; description: string; category: string; unit: string; is_public: boolean; is_active: boolean;
  max_per_order: number | null; members_only: boolean; show_exact_stock: boolean; tax_rate_bps: number | null; hsn_code: string;
  bundle_mode: boolean; variants: VariantDraft[]; component_input: { variant_id: number; quantity: number }[];
};

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });
const space = (ms: number) => `/admin/makerspaces/${ms}/shop`;

export const staffShopKeys = {
  all: (ms: number) => ["staff-shop", ms] as const,
  products: (ms: number, archived: boolean, page: number) => ["staff-shop", ms, "products", archived, page] as const,
  allProducts: (ms: number) => ["staff-shop", ms, "products", "all"] as const,
  product: (ms: number, id: number) => ["staff-shop", ms, "product", id] as const,
  movements: (ms: number, variantId: number | null) => ["staff-shop", ms, "movements", variantId] as const,
  settings: (ms: number) => ["staff-shop", ms, "settings"] as const,
  orders: (ms: number, filters: Record<string, string | number>) => ["staff-shop", ms, "orders", filters] as const,
  order: (ms: number, id: number) => ["staff-shop", ms, "order", id] as const,
  receipt: (ms: number, id: number) => ["staff-shop", ms, "receipt", id] as const,
  cash: (ms: number) => ["staff-shop", ms, "cash"] as const,
  report: (ms: number, from: string, to: string) => ["staff-shop", ms, "report", from, to] as const,
};

export function listProducts(ms: number, archived: boolean, page: number) {
  const query = new URLSearchParams({ page: String(page) });
  if (archived) query.set("archived", "true");
  return staffRequest<Paged<ShopProduct>>(`${space(ms)}/products/?${query}`);
}

/** Every live product, for the till and the stock list; follows pages up to a sane cap. */
export async function listAllProducts(ms: number) {
  const rows: ShopProduct[] = [];
  for (let page = 1; page <= 40; page += 1) {
    const result = await listProducts(ms, false, page);
    rows.push(...result.results);
    if (!result.next) break;
  }
  return rows;
}

export const fetchProduct = (id: number) => staffRequest<ShopProduct>(`/admin/shop/products/${id}/`);
export const createProduct = (ms: number, draft: ProductDraft & { price?: string }) =>
  staffRequest<ShopProduct>(`${space(ms)}/products/`, json("POST", draft));
export const updateProduct = (id: number, draft: Partial<ProductDraft>) =>
  staffRequest<ShopProduct>(`/admin/shop/products/${id}/`, json("PATCH", draft));
export const archiveProduct = (id: number) => staffRequest<void>(`/admin/shop/products/${id}/`, json("DELETE"));
export const archiveVariant = (id: number) => staffRequest<void>(`/admin/shop/variants/${id}/`, json("DELETE"));
export const productImageEndpoint = (id: number) => `/admin/shop/products/${id}/image/`;

export type StockMove = { kind: ShopStockMoveKindEnum; quantity: number; reason: string };
export const moveStock = (variantId: number, move: StockMove) =>
  staffRequest<ShopStaffVariant>(`/admin/shop/variants/${variantId}/stock/`, json("POST", move));
export function listMovements(ms: number, variantId: number | null) {
  const query = variantId ? `?variant_id=${variantId}` : "";
  return staffRequest<Paged<ShopMovement>>(`${space(ms)}/movements/${query}`);
}

export const fetchSettings = (ms: number) => staffRequest<ShopSettings>(`${space(ms)}/settings/`);
export const saveSettings = (ms: number, body: Partial<ShopSettings>) =>
  staffRequest<ShopSettings>(`${space(ms)}/settings/`, json("PATCH", body));

const MESSAGES: Record<string, string> = {
  setting_not_delegated: t`Only the Space Manager can change these shop settings here.`,
  setting_locked: t`These settings are locked by the platform and cannot be changed in this space.`,
  cash_session_closed: t`Open the cash drawer in Cash-up before taking cash.`,
  cash_session_open: t`A cash drawer is already open.`,
  cash_session_check: t`A second person must confirm this count.`,
  pickup_code_invalid: t`That pickup code does not match this order.`,
  order_not_collectable: t`This order cannot be collected yet. Take the payment or mark it ready first.`,
  order_not_payable: t`This order has nothing left to pay.`,
  order_not_cancellable: t`This order can no longer be cancelled.`,
  return_window_closed: t`The returns window for this order has closed.`,
  return_exceeds_sold: t`You cannot return more than was sold.`,
  price_changed: t`Prices changed. The basket has been re-priced; check the total and sell again.`,
  charges_off: t`Shop sales are not being recorded. Turn on “Track shop sales” first.`,
};

export function staffShopError(error: unknown) {
  if (!error) return "";
  if (!(error instanceof StructuredApiError)) return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
  if (error.code === "out_of_stock") {
    const available = Number(error.body.available ?? 0);
    return available > 0 ? t`${error.detail ?? "Not enough stock."} Only ${available} left.` : error.detail ?? t`Out of stock.`;
  }
  return (error.code && MESSAGES[error.code]) || error.detail || error.message;
}

export const errorCode = (error: unknown) => error instanceof StructuredApiError ? error.code : undefined;

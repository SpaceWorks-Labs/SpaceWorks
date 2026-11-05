import type {
  ShopBuyerOrder, ShopLineInput, ShopOrderCreate, ShopOrderPlaced, ShopPublicProduct, ShopPublicVariant, ShopQuote,
  ShopSummary,
} from "../../generated/api";
import { memberRequest, StructuredApiError, tenantMemberRequest, tenantPublicRequest } from "../../lib/api";

/** Release 2 L22: the public shop, the guest status page and a buyer's own orders. */
export type { ShopBuyerOrder, ShopLineInput, ShopPublicProduct, ShopPublicVariant, ShopQuote, ShopSummary };
export type Paged<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type OrderRequest = Omit<ShopOrderCreate, "lines"> & { lines: ShopLineInput[] };

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body),
  headers: { "Content-Type": "application/json" } });
const base = (slug: string) => `/public/m/${encodeURIComponent(slug)}/shop`;

export const shopKeys = {
  summary: (slug: string) => ["shop", slug, "summary"] as const,
  products: (slug: string, page: number, category: string) => ["shop", slug, "products", page, category] as const,
  product: (slug: string, productSlug: string) => ["shop", slug, "product", productSlug] as const,
  quote: (slug: string, signedIn: boolean, lines: ShopLineInput[]) => ["shop", slug, "quote", signedIn, lines] as const,
  status: (slug: string, token: string) => ["shop", slug, "status", token] as const,
  memberOrders: (makerspaceId: number, page: number) => ["member-shop-orders", makerspaceId, page] as const,
  memberOrder: (orderId: number) => ["member-shop-order", orderId] as const,
};

export const fetchShop = (slug: string) => tenantPublicRequest<ShopSummary>(slug, `${base(slug)}/`);
export function fetchProducts(slug: string, page: number, category: string) {
  const query = new URLSearchParams({ page: String(page) });
  if (category) query.set("category", category);
  return tenantPublicRequest<Paged<ShopPublicProduct>>(slug, `${base(slug)}/products/?${query}`);
}
export const fetchProduct = (slug: string, productSlug: string) =>
  tenantPublicRequest<ShopPublicProduct>(slug, `${base(slug)}/products/${encodeURIComponent(productSlug)}/`);

/** A signed-in buyer goes through the member session (refresh-and-retry) so member prices apply. */
function shopPost<T>(slug: string, path: string, body: unknown, signedIn: boolean) {
  return signedIn ? tenantMemberRequest<T>(slug, path, post(body)) : tenantPublicRequest<T>(slug, path, post(body));
}
export const quoteCart = (slug: string, lines: ShopLineInput[], signedIn: boolean) =>
  shopPost<ShopQuote>(slug, `${base(slug)}/quote/`, { lines }, signedIn);
export const requestEmailCode = (slug: string, email: string) =>
  tenantPublicRequest<void>(slug, `${base(slug)}/email-code/`, post({ email }));
export const placeShopOrder = (slug: string, body: OrderRequest, signedIn: boolean) =>
  shopPost<ShopOrderPlaced>(slug, `${base(slug)}/orders/`, body, signedIn);
export const fetchOrderStatus = (slug: string, token: string) =>
  tenantPublicRequest<ShopBuyerOrder>(slug, `${base(slug)}/orders/${encodeURIComponent(token)}/`);

export function listMemberShopOrders(makerspaceId: number, page: number) {
  const query = new URLSearchParams({ makerspace_id: String(makerspaceId), page: String(page) });
  return memberRequest<Paged<ShopBuyerOrder>>(`/member/shop/orders/?${query}`);
}
export const fetchMemberShopOrder = (orderId: number) => memberRequest<ShopBuyerOrder>(`/member/shop/orders/${orderId}/`);
export const cancelMemberShopOrder = (orderId: number) =>
  memberRequest<ShopBuyerOrder>(`/member/shop/orders/${orderId}/cancel/`, post({}));

/** Money exactly as the server computed it: the browser never re-prices. */
export function shopMoney(amount: string | number | null | undefined, currency: string) {
  const value = Number(amount ?? 0);
  try { return new Intl.NumberFormat(undefined, { style: "currency", currency: currency.toUpperCase() }).format(value); }
  catch { return `${value.toFixed(2)} ${currency.toUpperCase()}`; }
}

export function priceRange(product: Pick<ShopPublicProduct, "price_from" | "price_to">, currency: string) {
  if (!product.price_from) return "";
  if (product.price_to && product.price_to !== product.price_from) {
    return `${shopMoney(product.price_from, currency)} – ${shopMoney(product.price_to, currency)}`;
  }
  return shopMoney(product.price_from, currency);
}

type Tone = "success" | "warn" | "danger" | "neutral" | "info";
/** "In stock / Low / Sold out"; an exact count only when the product opted in and the server sent one. */
export function stockLabel(variant: Pick<ShopPublicVariant, "sold_out" | "stock_label" | "stock_count">): { label: string; tone: Tone } | null {
  if (variant.sold_out || variant.stock_label === "sold_out") return { label: "Sold out", tone: "danger" };
  const count = variant.stock_count !== null && variant.stock_count !== undefined ? ` · ${variant.stock_count} left` : "";
  if (variant.stock_label === "low") return { label: `Low${count}`, tone: "warn" };
  if (variant.stock_label === "in_stock") return { label: `In stock${count}`, tone: "success" };
  return null;
}

export function variantLabel(product: Pick<ShopPublicProduct, "name" | "variants">, variant: Pick<ShopPublicVariant, "name">) {
  return product.variants.length > 1 && variant.name ? `${product.name} · ${variant.name}` : product.name;
}

export const ORDER_STATUS: Record<string, { label: string; tone: Tone }> = {
  held: { label: "Held for you", tone: "warn" }, awaiting_payment: { label: "Awaiting payment", tone: "warn" },
  paid: { label: "Paid", tone: "info" }, ready: { label: "Ready to collect", tone: "success" },
  collected: { label: "Collected", tone: "success" }, cancelled: { label: "Cancelled", tone: "neutral" },
  unfulfilled: { label: "Could not be filled", tone: "danger" }, refunded: { label: "Refunded", tone: "neutral" },
};
export const orderStatus = (status: string) => ORDER_STATUS[status] ?? { label: status, tone: "neutral" as Tone };
export const isUnpaid = (status: string) => status === "held" || status === "awaiting_payment";

const MESSAGES: Record<string, string> = {
  price_changed: "Prices changed since you looked. Check the new total and confirm again.",
  per_order_limit: "That is more than one order may take of this item.",
  member_only: "Some of these items are for members only. Sign in with your membership to buy them.",
  shop_closed: "The shop is closed right now.",
  feature_off: "The shop is closed right now.",
  hold_expired: "Your hold ran out. Review the order and place it again.",
  item_unavailable: "One of these items is no longer on sale.",
  pickup_event_invalid: "That event is no longer open for pickups. Choose another.",
};

export function shopErrorMessage(error: unknown, labelFor?: (variantId: number) => string) {
  if (!error) return "";
  if (!(error instanceof StructuredApiError)) return "Something went wrong. Try again.";
  if (error.code === "out_of_stock") {
    const available = Number(error.body.available ?? 0);
    const name = labelFor?.(Number(error.body.variant_id)) || "One item";
    return available > 0 ? `${name}: only ${available} left. Lower the quantity and try again.` : `${name} has just sold out.`;
  }
  return (error.code && MESSAGES[error.code]) || error.detail || error.message;
}

/** A 409 price_changed carries the server's new quote; the buyer confirms it before paying. */
export function changedQuote(error: unknown): ShopQuote | null {
  if (!(error instanceof StructuredApiError) || error.code !== "price_changed") return null;
  const quote = error.body.quote as ShopQuote | undefined;
  return quote && typeof quote === "object" && "digest" in quote ? quote : null;
}

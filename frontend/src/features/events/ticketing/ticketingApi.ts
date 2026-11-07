import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { memberRequest, tenantPublicRequest } from "../../../lib/api";

/** Release 2 L6: paid ticketing v2 -- the public shop, member orders, claims and transfers. */

export type ShopTicket = {
  id: number; name: string; amount: string; audience: "member" | "public"; pricing_mode: "fixed" | "pwyw";
  min_amount: string; seats_per_ticket: number; min_quantity: number; per_order_limit: number;
  spots_left: number | null; sold_out: boolean; next_tier: { name: string; amount: string } | null;
};
export type ShopAddon = {
  id: number; name: string; description: string; kind: string; amount: string; per_order_limit: number;
  sold_out: boolean; variants: { id: number; label: string; sold_out: boolean }[];
};
export type RefundPolicySummary = {
  text: string; overridden: boolean;
  terms: { full_before_minutes: string; partial_before_minutes: string; partial_percent: string; cancellation_fee: string } | null;
};
export type TicketShop = {
  event_id: number; orders_enabled: boolean; currency: string; ticket_types: ShopTicket[]; addons: ShopAddon[];
  booking_fee_fixed: string; booking_fee_bps: number; max_tickets_per_order: number; promo_codes_enabled: boolean;
  policy: RefundPolicySummary;
};
export type QuoteLine = { component: string; label: string; quantity: string; unit_amount: string; gross: string;
  discount: string; net: string; detail: Record<string, unknown> };
export type OrderQuote = {
  quote: { currency: string; lines: QuoteLine[]; subtotal: string; discount_total: string; total: string; digest: string };
  promo_saving: string | null; seats: number; policy: RefundPolicySummary;
};
export type OrderSeat = { id: number; event_id: number; ticket_type_id: number | null; status: "unclaimed" | "claimed" | "void";
  attendee_email: string; registration_id: number | null; invited_at: string | null; claimed_at: string | null };
export type OrderLine = { id: number; kind: string; label: string; quantity: number; unit_amount: string; line_total: string };
export type TicketOrder = {
  id: number; kind: "tickets" | "pass" | "type_change"; status: "pending" | "paid" | "cancelled" | "expired" | "unfulfilled";
  event: number | null; series: number | null; event_title: string; currency: string; subtotal: string;
  discount_total: string; fee_total: string; total: string; created_at: string; paid_at: string | null;
  lines: OrderLine[]; seats: OrderSeat[]; checkout_url: string; payment_status: string | null;
  payment_disputed: boolean; hold_expires_at: string | null;
};
export type OrderRequest = {
  tickets: { ticket_type_id: number; quantity: number; amount?: string }[];
  addons?: { addon_id: number; variant_id?: number | null; quantity: number }[];
  promo_code?: string; access_codes?: string[]; buyer_attends?: boolean; attendees?: string[]; digest?: string;
};
export type ClaimPreview = { event_id: number; makerspace_id: number; event_title: string; starts_at: string;
  ticket_type: string; from_name: string; email_matches: boolean };

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body),
  headers: { "Content-Type": "application/json" } });
const shopPath = (slug: string, token: string) =>
  `/public/${encodeURIComponent(slug)}/events/${encodeURIComponent(token)}/tickets/`;

export const ticketingKeys = {
  shop: (slug: string, token: string) => ["event-ticket-shop", slug, token] as const,
  orders: (makerspaceId: number) => ["member-orders", makerspaceId] as const,
  order: (makerspaceId: number, orderId: number) => ["member-order", makerspaceId, orderId] as const,
  claim: (kind: "claim" | "transfer", token: string) => ["ticket-claim", kind, token] as const,
};

export const fetchShop = (slug: string, token: string) => tenantPublicRequest<TicketShop>(slug, shopPath(slug, token));
/** Access codes reveal hidden tickets; sent in a POST body, never in a URL. */
export const unlockShop = (slug: string, token: string, codes: string[]) =>
  tenantPublicRequest<TicketShop>(slug, shopPath(slug, token), json({ access_codes: codes }));
export const quoteOrder = (makerspaceId: number, eventId: number, body: OrderRequest) =>
  memberRequest<OrderQuote>(`/member/makerspaces/${makerspaceId}/events/${eventId}/orders/quote/`, json(body));
export const placeOrder = (makerspaceId: number, eventId: number, body: OrderRequest) =>
  memberRequest<{ order: TicketOrder; checkout_url: string }>(`/member/makerspaces/${makerspaceId}/events/${eventId}/orders/`, json(body));
export const listOrders = (makerspaceId: number) =>
  memberRequest<{ results: TicketOrder[] }>(`/member/makerspaces/${makerspaceId}/orders/`);
export const fetchOrder = (makerspaceId: number, orderId: number) =>
  memberRequest<TicketOrder>(`/member/makerspaces/${makerspaceId}/orders/${orderId}/`);
const orderAction = (makerspaceId: number, orderId: number, action: string, body: unknown = {}) =>
  memberRequest<TicketOrder>(`/member/makerspaces/${makerspaceId}/orders/${orderId}/${action}/`, json(body));
export const assignAttendees = (makerspaceId: number, orderId: number, assignments: Record<string, string>) =>
  orderAction(makerspaceId, orderId, "attendees", { assignments });
export const chaseAttendees = (makerspaceId: number, orderId: number) => orderAction(makerspaceId, orderId, "chase");
export const cancelOrder = (makerspaceId: number, orderId: number) => orderAction(makerspaceId, orderId, "cancel");
export const claimOwnSeat = (makerspaceId: number, orderId: number, seatId: number) =>
  memberRequest<{ registration_id: number }>(`/member/makerspaces/${makerspaceId}/orders/${orderId}/seats/${seatId}/claim/`, json({}));
const claimPath = (kind: "claim" | "transfer", token: string) =>
  `/member/${kind === "claim" ? "ticket-claims" : "ticket-transfers"}/${encodeURIComponent(token)}/`;
export const previewClaim = (kind: "claim" | "transfer", token: string) => memberRequest<ClaimPreview>(claimPath(kind, token));
export const acceptClaim = (kind: "claim" | "transfer", token: string) =>
  memberRequest<{ registration_id: number; event_id: number; status: string }>(claimPath(kind, token), json({}));

/** Money shown as the server computed it: never re-priced in the browser. */
export function money(amount: string | number, currency: string) {
  const value = Number(amount);
  if (!value) return "Free";
  try { return new Intl.NumberFormat(formatLocale(), { style: "currency", currency: currency.toUpperCase() }).format(value); }
  catch { return `${value.toFixed(2)} ${currency.toUpperCase()}`; }
}

export function policyLine(policy: RefundPolicySummary) {
  if (!policy.terms) return policy.text || "Refunds are decided by the organisers case by case.";
  const hours = (minutes: string) => Math.round(Number(minutes) / 60);
  const parts = [`Full refund until ${hours(policy.terms.full_before_minutes)} h before the start`];
  if (Number(policy.terms.partial_percent) > 0) {
    parts.push(`${policy.terms.partial_percent}% until ${hours(policy.terms.partial_before_minutes)} h before`);
  }
  return [parts.join(", ") + ".", policy.text].filter(Boolean).join(" ");
}

export const ORDER_STATUS: Record<TicketOrder["status"], { label: string; tone: "success" | "warn" | "neutral" | "danger" }> = {
  pending: { label: t`Awaiting payment`, tone: "warn" }, paid: { label: t`Paid`, tone: "success" },
  cancelled: { label: t`Cancelled`, tone: "neutral" }, expired: { label: t`Checkout expired`, tone: "neutral" },
  unfulfilled: { label: t`Could not be seated`, tone: "danger" },
};

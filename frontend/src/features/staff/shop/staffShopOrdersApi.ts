import { t } from "@lingui/core/macro";
import type { ShopCashSession, ShopQuote, ShopReceipt, ShopStaffOrder } from "../../../generated/api";
import { staffRequest } from "../../../lib/api";
import type { Paged } from "./staffShopApi";

/** Release 2 L22: orders at the desk, the till, receipts, cash sessions and the shop report. */
export type { ShopCashSession, ShopQuote, ShopReceipt, ShopStaffOrder };
export type PayMethod = "cash" | "upi" | "card_machine";
export type Line = { variant_id: number; quantity: number };
export type ShopReport = {
  currency: string;
  totals: { orders: number; sales: string; refunds: string; net: string; tax: string };
  by_channel: { channel: string; orders: number; sales: string }[];
  by_method: { method: string; amount: string }[];
  by_month: { month: string; sales: string; refunds: string }[];
  top_items: { label: string; quantity: number; sales: string }[];
};

const post = (body: unknown = {}): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const space = (ms: number) => `/admin/makerspaces/${ms}/shop`;
const order = (id: number) => `/admin/shop/orders/${id}`;

export const METHOD_LABELS: Record<string, string> = { cash: t`Cash`, upi: "UPI", card_machine: t`Card machine`, online: t`Online` };
export const CHANNEL_LABELS = (): Record<string, string> => ({ online: t`Online`, pos: t`Desk sale` });

/** SH2 adds `buyer` (account id) and `product` (catalogue product id) to the queue's filters. */
export function listOrders(ms: number, filters: { status?: string; channel?: string; code?: string; buyer?: string; product?: string; page: number }) {
  const query = new URLSearchParams({ page: String(filters.page) });
  for (const key of ["status", "channel", "code", "buyer", "product"] as const) if (filters[key]) query.set(key, String(filters[key]));
  return staffRequest<Paged<ShopStaffOrder>>(`${space(ms)}/orders/?${query}`);
}
export const fetchOrder = (id: number) => staffRequest<ShopStaffOrder>(`${order(id)}/`);
export const movePickupToSpace = (id: number) => staffRequest<ShopStaffOrder>(`${order(id)}/move-pickup-to-space/`, post());
export const markReady = (id: number) => staffRequest<ShopStaffOrder>(`${order(id)}/ready/`, post());
export const collectOrder = (id: number, pickupCode: string) =>
  staffRequest<ShopStaffOrder>(`${order(id)}/collect/`, post({ pickup_code: pickupCode }));
export const takePayment = (id: number, body: { method: PayMethod; reference: string; hand_over: boolean }) =>
  staffRequest<ShopStaffOrder>(`${order(id)}/take-payment/`, post(body));
export const cancelOrder = (id: number, reason: string) => staffRequest<ShopStaffOrder>(`${order(id)}/cancel/`, post({ reason }));
export type ReturnRow = { line_id: number; quantity: number; disposition: "restock" | "write_off" };
export const returnItems = (id: number, rows: ReturnRow[], reason: string) =>
  staffRequest<ShopStaffOrder>(`${order(id)}/returns/`, post({ rows, reason }));
export const fetchReceipt = (id: number) => staffRequest<ShopReceipt>(`${order(id)}/receipt/`);
export const emailReceipt = (id: number, email: string) =>
  staffRequest<void>(`${order(id)}/receipt/`, post(email ? { email } : {}));

export const posQuote = (ms: number, lines: Line[], memberId: number | null) =>
  staffRequest<ShopQuote>(`${space(ms)}/pos/quote/`, post({ lines, member_id: memberId }));
export type SaleBody = { lines: Line[]; member_id: number | null; method: PayMethod; reference: string; quote_digest: string;
  receipt_email?: string };
export const posSale = (ms: number, body: SaleBody) => staffRequest<ShopStaffOrder>(`${space(ms)}/pos/sale/`, post(body));
export const findMembers = (ms: number, q: string) =>
  staffRequest<{ id: number; name: string }[]>(`${space(ms)}/members/?${new URLSearchParams({ q })}`);

export const listCashSessions = (ms: number) => staffRequest<Paged<ShopCashSession>>(`${space(ms)}/cash-sessions/`);
export const openCash = (ms: number, openingFloat: string) =>
  staffRequest<ShopCashSession>(`${space(ms)}/cash-sessions/`, post({ opening_float: openingFloat }));
export const closeCash = (id: number, countedCash: string, note: string) =>
  staffRequest<ShopCashSession>(`/admin/shop/cash-sessions/${id}/close/`, post({ counted_cash: countedCash, note }));
export const confirmCash = (id: number) => staffRequest<ShopCashSession>(`/admin/shop/cash-sessions/${id}/confirm/`, post());

export function fetchReport(ms: number, from: string, to: string) {
  return staffRequest<ShopReport>(`${space(ms)}/report/?${new URLSearchParams({ from, to })}`);
}

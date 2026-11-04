import { memberRequest } from "../../../lib/api";
import type { TicketOrder } from "./ticketingApi";

/** Release 2 L6 member screens: transfer a ticket, change its type, buy a series pass. */

export type TransferOffer = { id: number; status: string; expires_at: string };
export type TypeChangeResult = {
  status: "changed" | "payment_required"; registration_id: number; order: TicketOrder | null; checkout_url: string;
};
export type PassType = {
  id: number; name: string; amount: string; capacity: number | null; occurrence_refund_amount: string;
  sales_end_at: string | null; is_active: boolean;
};

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body),
  headers: { "Content-Type": "application/json" } });
const registrationPath = (makerspaceId: number, registrationId: number) =>
  `/member/makerspaces/${makerspaceId}/event-registrations/${registrationId}`;
const passPath = (makerspaceId: number, seriesId: number) =>
  `/member/makerspaces/${makerspaceId}/event-series/${seriesId}/passes/`;

export const transferTicket = (makerspaceId: number, registrationId: number, email: string) =>
  memberRequest<TransferOffer>(`${registrationPath(makerspaceId, registrationId)}/transfer/`, post({ email }));
export const changeTicketType = (makerspaceId: number, registrationId: number, ticketTypeId: number, digest?: string) =>
  memberRequest<TypeChangeResult>(`${registrationPath(makerspaceId, registrationId)}/change-type/`,
    post({ ticket_type_id: ticketTypeId, ...(digest ? { digest } : {}) }));
export const listSeriesPasses = (makerspaceId: number, seriesId: number) =>
  memberRequest<PassType[]>(passPath(makerspaceId, seriesId));
export const buySeriesPass = (makerspaceId: number, seriesId: number, passTypeId: number) =>
  memberRequest<{ order: TicketOrder; checkout_url: string }>(passPath(makerspaceId, seriesId), post({ pass_type_id: passTypeId }));

/** Only a real web address leaves the app for checkout; anything else is never linked. */
export function safeCheckoutUrl(url: string | null | undefined) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

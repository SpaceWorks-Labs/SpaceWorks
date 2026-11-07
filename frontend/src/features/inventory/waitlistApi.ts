import { formatLocale } from "../../lib/format";
import { memberRequest, staffRequest } from "../../lib/api";

/** A place in an item's loan waitlist (`loans.waitlist`). `position` is set only while waiting. */
export type WaitlistEntry = {
  id: number;
  product: number;
  product_name: string;
  quantity: number;
  status: "waiting" | "offered" | "claimed";
  position: number | null;
  offered_at: string | null;
  offer_expires_at: string | null;
  created_at: string;
  /** Staff list only: who holds the place. */
  member_name?: string;
};

export const waitlistKeys = {
  member: (makerspaceId: number) => ["member", "waitlist", makerspaceId] as const,
  staff: (makerspaceId: number, productId: number) => ["staff-waitlist", makerspaceId, productId] as const,
};

const memberBase = (makerspaceId: number) => `/member/makerspaces/${makerspaceId}/waitlist`;

export const waitlistApi = {
  mine: (makerspaceId: number) => memberRequest<WaitlistEntry[]>(memberBase(makerspaceId)),
  join: (makerspaceId: number, productId: number, quantity = 1) =>
    memberRequest<WaitlistEntry>(memberBase(makerspaceId), { method: "POST", body: JSON.stringify({ product_id: productId, quantity }) }),
  leave: (makerspaceId: number, entryId: number) =>
    memberRequest<WaitlistEntry>(`${memberBase(makerspaceId)}/${entryId}/leave`, { method: "POST", body: JSON.stringify({}) }),
  forItem: (makerspaceId: number, productId: number) =>
    staffRequest<WaitlistEntry[]>(`/admin/makerspace/${makerspaceId}/waitlist?product=${productId}`),
};

export function formatWhen(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
}

import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";

/**
 * Decision 242(e) / PE1: the staff member 360 (`admin/makerspaces/{id}/members/{uid}/activity`).
 * Hand-typed from backend/apps/admin_api/views_member_activity.py (MemberActivitySerializer) until
 * the generated client is regenerated. Any staff viewer the server answers with 200 sees the counts;
 * `rows` arrive only for areas that viewer manages.
 */
export type MemberActivityArea = "lending" | "bookings" | "machines" | "events" | "shop" | "money" | "safety" | "people";
export type MemberActivityRow = {
  id: number; label: string; status: string; at: string | null;
  link: { tab: string; filters: Record<string, string> };
};
export type MemberActivityBlock = {
  area: MemberActivityArea; count: number; rows_visible: boolean; rows: MemberActivityRow[] | null;
  open?: number; pending?: number; owed?: Record<string, string>;
  guest_passes?: number; volunteer_entries?: number; certifications?: number;
};
export type MemberActivity = {
  member_id: number; areas: MemberActivityBlock[]; errors: string[];
  /** A26: restriction state, and false for an account-only borrower (no membership here). */
  access_status?: "active" | "restricted" | "suspended"; is_member?: boolean;
};

export const AREA_LABELS: Record<MemberActivityArea, string> = {
  // Decision 247: the `lending` area key reads as "Inventory" everywhere.
  lending: t`Inventory`, bookings: t`Bookings`, machines: t`Machine jobs and sessions`, events: t`Events`,
  shop: t`Shop orders`, money: t`Payments`, safety: t`Incidents`, people: t`Guests and volunteering`,
};

/** Where each area's "see all" link lands, narrowed to this member where that list can be. */
export function areaTarget(area: MemberActivityArea, userId: number): { tab: string; query: Record<string, string | number>; subPath?: string } {
  switch (area) {
    case "lending": return { tab: "requests", query: {} };
    case "bookings": return { tab: "bookings", query: {} };
    case "machines": return { tab: "machines", query: {} };
    case "events": return { tab: "events", query: {} };
    case "shop": return { tab: "shop", query: { buyer: userId }, subPath: "orders" };
    case "money": return { tab: "payments", query: {} };
    case "safety": return { tab: "incidents", query: { person: userId } };
    case "people": return { tab: "members", query: { section: "guests" } };
  }
}

/** A row's own link; the server now names real console tabs. */
export function rowTarget(row: MemberActivityRow): { tab: string; query: Record<string, string>; subPath?: string } {
  if (row.link.tab === "shop") return { tab: "shop", query: row.link.filters, subPath: "orders" };
  if (row.link.tab === "incidents" && row.link.filters.id) return { tab: "incidents", query: { incident: row.link.filters.id } };
  return { tab: row.link.tab, query: row.link.filters };
}

export function useMemberActivity(makerspaceId: number, userId: number, enabled = true) {
  return useQuery({
    queryKey: ["member-activity", makerspaceId, userId],
    enabled,
    retry: false,
    queryFn: ({ signal }) => staffRequest<MemberActivity>(`/admin/makerspaces/${makerspaceId}/members/${userId}/activity`, { signal }),
  });
}

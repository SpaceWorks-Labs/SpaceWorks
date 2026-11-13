import { t } from "@lingui/core/macro";
import { staffRequest } from "../../../lib/api";

// Decision 242(l): superadmin-only, counts only, platform session. Hand-typed until the integrator
// regenerates the OpenAPI client (admin_api/views_platform_cross_space.py).
export type QueueCounts = Record<string, number>;
export type QueueRow = { id: number; name: string; slug: string; counts: QueueCounts; total: number };
export type UsageResource = { key?: string; label: string; used: number | null; limit: number | null; unit?: "bytes" | "count" };
export type SpaceSnapshot = { id: number; name: string; slug: string; hosted: boolean; counts: QueueCounts;
  usage: { resources?: UsageResource[] } & Record<string, unknown> };
export type InboxRow = { id: number; name: string; personal_unread: number; notices_unread: number };
export type SearchHit = { kind: "space" | "person" | "receipt"; label: string; space_id?: number; account_id?: number; space_ids?: number[] };

const PLATFORM = "platform" as const;
export const crossSpaceKeys = {
  queues: ["platform-cross", "queues"] as const,
  snapshot: (id: number) => ["platform-cross", "snapshot", id] as const,
  inbox: ["platform-cross", "inbox"] as const,
  search: (term: string) => ["platform-cross", "search", term] as const,
};

export const getQueues = () => staffRequest<{ spaces: QueueRow[] }>("/admin/platform/queues", {}, PLATFORM);
export const getSnapshot = (id: number) => staffRequest<SpaceSnapshot>(`/admin/platform/spaces/${id}/snapshot`, {}, PLATFORM);
export const getInbox = () => staffRequest<{ spaces: InboxRow[]; total: number }>("/admin/platform/inbox", {}, PLATFORM);
export const searchPlatform = (term: string, signal?: AbortSignal) =>
  staffRequest<{ results: SearchHit[] }>(`/admin/platform/search?q=${encodeURIComponent(term)}`, { signal }, PLATFORM);

/** Plain names for the server's METRICS (platform_cross_space.py). */
export function metricLabel(key: string) {
  const labels: Record<string, string> = {
    pending_requests: t`Borrow requests to review`, awaiting_issue: t`Ready to hand out`, overdue_loans: t`Overdue loans`,
    pending_bookings: t`Bookings to approve`, pending_registrations: t`Registrations to approve`,
    refund_cases_open: t`Refunds to decide`, paid_claims_open: t`"I paid" claims to check`, open_incidents: t`Open incidents`,
    critical_incidents: t`Serious incidents`, open_booking_issues: t`Booking problems`, shop_orders_waiting: t`Shop orders waiting`,
    pending_payments: t`Payments not yet paid`,
  };
  return labels[key] ?? key.replace(/_/g, " ");
}

/** The table's columns: approvals combined, then the counts a superadmin chases first. */
export const QUEUE_COLUMNS: { key: string; label: () => string; keys: string[]; urgent?: boolean }[] = [
  { key: "approvals", label: () => t`Waiting for approval`, keys: ["pending_requests", "pending_bookings", "pending_registrations"] },
  { key: "awaiting_issue", label: () => t`Ready to hand out`, keys: ["awaiting_issue"] },
  { key: "overdue_loans", label: () => t`Overdue loans`, keys: ["overdue_loans"], urgent: true },
  { key: "money", label: () => t`Refunds and claims`, keys: ["refund_cases_open", "paid_claims_open"] },
  { key: "pending_payments", label: () => t`Unpaid charges`, keys: ["pending_payments"] },
  { key: "shop", label: () => t`Shop orders`, keys: ["shop_orders_waiting"] },
  { key: "safety", label: () => t`Open incidents`, keys: ["open_incidents"], urgent: true },
  { key: "critical", label: () => t`Serious incidents`, keys: ["critical_incidents"], urgent: true },
  { key: "booking_issues", label: () => t`Booking problems`, keys: ["open_booking_issues"] },
];

export const sumKeys = (counts: QueueCounts, keys: string[]) => keys.reduce((total, key) => total + (counts[key] ?? 0), 0);

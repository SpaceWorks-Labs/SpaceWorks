import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../../../lib/api/sessionContext";
import { staffTabPath } from "../../staffTabs";

/** Hand-typed until the integrator regenerates the OpenAPI client (operations/serializers_attention.py). */
export type AttentionLink = { tab: string; filters: Record<string, string> };
export type AttentionItem = { key: string; count: number; link: AttentionLink };
export type AttentionArea = { key: string; total: number; items: AttentionItem[] };
export type Attention = { areas: AttentionArea[]; waiting: (AttentionItem & { area: string })[]; errors: string[] };

export type AttentionRouting = { slug: string; guestOnly: boolean; singleTenantLocked: boolean; allowedTabs?: readonly string[] };

/** Plain area names. The `lending` key is shown as "Inventory" (decision 247). */
export function areaLabel(key: string) {
  const labels: Record<string, string> = {
    lending: t`Inventory`, machines: t`Machines`, events: t`Events`, bookings: t`Bookings`, shop: t`Shop`,
    people: t`People`, money: t`Money`, safety: t`Safety`, repairs: t`Repairs`,
  };
  return labels[key] ?? humanize(key);
}

const ITEM_LABELS = (): Record<string, string> => ({
  pending_requests: t`Borrow requests to review`, awaiting_issue: t`Ready to hand out`, overdue_loans: t`Overdue loans`,
  due_today_loans: t`Due back today`, due_soon_loans: t`Due back soon`, open_problem_reports: t`Problem reports`,
  true_low_stock: t`Low stock`, in_repair: t`Items in repair`, stocktakes_awaiting_approval: t`Stocktakes to approve`,
  machines_down: t`Machines down`, jobs_to_review: t`Jobs to review`, jobs_in_progress: t`Jobs in progress`,
  jobs_awaiting_collection: t`Jobs ready to collect`, maintenance_overdue: t`Maintenance overdue`,
  certifications_expiring: t`Certifications ending within 30 days`, my_open_repairs: t`My open repairs`,
  my_work_orders: t`My work orders`, pending_event_registrations: t`Registrations to approve`,
  waitlisted_registrations: t`People on a waitlist`, events_today: t`Events today`, pending_bookings: t`Bookings to approve`,
  bookings_today: t`Bookings today`, open_booking_issues: t`Booking problems`, room_outages_week: t`Rooms out of use this week`,
  shop_awaiting_payment: t`Orders waiting for payment`, shop_to_prepare: t`Orders to prepare`,
  shop_ready_for_pickup: t`Orders ready for pickup`, shop_unfulfilled: t`Orders we couldn't fill`,
  membership_requests: t`Membership requests`, erasure_requests: t`Requests to delete personal data`,
  guest_passes_today: t`Guest passes today`, volunteer_hours_pending: t`Volunteer hours to approve`,
  payments_pending: t`Payments not yet paid`, payments_overdue: t`Payments overdue`,
  paid_claims_waiting: t`"I paid" claims to check`, refund_cases_open: t`Refunds to decide`, open_incidents: t`Open incidents`,
});

export function itemLabel(key: string) {
  return ITEM_LABELS()[key] ?? humanize(key);
}

const URGENT = new Set(["overdue_loans", "machines_down", "maintenance_overdue", "payments_overdue", "open_incidents", "open_problem_reports"]);
export const isUrgent = (key: string) => URGENT.has(key);

/** A deep link for a counter, or undefined when the viewer cannot open that tab here. */
export function attentionHref(raw: AttentionLink, routing: AttentionRouting) {
  const link = raw;
  if (routing.allowedTabs && !routing.allowedTabs.includes(link.tab)) return undefined;
  const query = new URLSearchParams(link.filters).toString();
  const path = staffTabPath(link.tab, routing.guestOnly, routing.slug, routing.singleTenantLocked);
  return consoleSessionHref(query ? `${path}?${query}` : path);
}

function humanize(key: string) {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

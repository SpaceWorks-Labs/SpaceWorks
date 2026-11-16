import { staffTabPath } from "../staffTabs";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
const destinations: Record<string, { tab: string; filters: Record<string, string> }> = {
  upcoming_events: { tab: "events", filters: { status: "published" } },
  // Open item A22: the cross-event queue of pending approvals and waitlisted places.
  pending_event_registrations: { tab: "events", filters: { eventsView: "queue" } },
  pending_bookings: { tab: "bookings", filters: { status: "pending" } },
  upcoming_bookings: { tab: "bookings", filters: { status: "confirmed" } },
  open_booking_issues: { tab: "bookings", filters: { view: "issues" } },
  // Open item A24 tiles; their list filters are tuned by the links lane (G1).
  today_events: { tab: "events", filters: {} },
  today_check_ins: { tab: "events", filters: {} },
  today_bookings: { tab: "bookings", filters: {} },
  room_outages_week: { tab: "bookings", filters: {} },
  // Decision 224(a) gave the accountability page to the people area (manage_members). Overdue
  // loans and problem reports stay the lending area's, so they open its own lists instead.
  overdue_loans: { tab: "ledger", filters: { overdue: "true" } },
  pending_requests: { tab: "requests", filters: { queue: "pending" } },
  awaiting_issue: { tab: "requests", filters: { queue: "accepted" } },
  open_problem_reports: { tab: "needsfix", filters: { section: "problems" } },
  low_stock: { tab: "inventory", filters: { out_of_stock: "true", archived: "all" } },
  // Decision 242: the same targets the server's attention counters name (dashboard_attention.py).
  due_today_loans: { tab: "ledger", filters: { due: "today" } },
  due_soon_loans: { tab: "ledger", filters: { due: "soon" } },
  true_low_stock: { tab: "inventory", filters: { low_stock: "true" } },
  in_repair: { tab: "needsfix", filters: {} },
  payments_to_record: { tab: "payments", filters: { status: "pending" } },
  pending_prints: { tab: "machines", filters: { work_queue: "pending_prints" } },
  active_prints: { tab: "machines", filters: { work_queue: "active_prints" } },
  prints_awaiting_collection: { tab: "machines", filters: { work_queue: "prints_awaiting_collection" } },
  failed_emails: { tab: "email-logs", filters: { status: "failed", recent_days: "7" } },
  stocktakes_awaiting_approval: { tab: "stocktake", filters: { status: "completed" } },
  warranty_expiring: { tab: "warranty", filters: {} },
  maintenance_overdue: { tab: "machines", filters: { work_queue: "maintenance_overdue" } },
  pending_payments: { tab: "payments", filters: { status: "pending" } },
};

export function dashboardDestination(key: string) { return destinations[key]; }
export function dashboardHref(key: string, slug: string, single = false, guest = false, today = new Date()) {
  const destination = destinations[key];
  if (!destination) return "";
  const filters = { ...destination.filters };
  if (key === "warranty_expiring") { const date = new Date(today); date.setDate(date.getDate() + 30); filters.expires_before = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`; }
  return consoleSessionHref(`${staffTabPath(destination.tab, guest, slug, single)}?${new URLSearchParams(filters)}`);
}

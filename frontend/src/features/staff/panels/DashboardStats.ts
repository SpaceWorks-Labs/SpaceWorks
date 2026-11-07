import { t } from "@lingui/core/macro";
import type { Dashboard } from "../../../generated/api";
export type DashboardCounts = Omit<Dashboard, "widgets" | "queue_tiles" | "outstanding_by_currency" | "next_up_events">;

// Tiles keep their semantic intent; only emphasis is a filled attention pill.
// Numbers and labels otherwise sit on neutral panels.
type Tone = "accent" | "emphasis" | "success" | "warn" | "danger";

type Tile = {
  key: Exclude<keyof DashboardCounts, "scope_mode">;
  label: string;
  actionNeeded: boolean;
  tone: Tone;
};

// Ordered by what a makerspace acts on first: loans and requests, then money,
// then events and bookings, then machines and housekeeping.
export const TILES: Tile[] = [
  { key: "pending_requests", label: t`Pending requests`, actionNeeded: true, tone: "warn" },
  { key: "awaiting_issue", label: t`Awaiting issue`, actionNeeded: true, tone: "warn" },
  { key: "overdue_loans", label: t`Overdue loans`, actionNeeded: true, tone: "danger" },
  { key: "open_problem_reports", label: t`Problem reports`, actionNeeded: true, tone: "danger" },
  { key: "low_stock", label: t`Out of stock`, actionNeeded: true, tone: "danger" },
  { key: "pending_payments", label: t`Pending payments`, actionNeeded: true, tone: "emphasis" },
  { key: "pending_event_registrations", label: t`Registrations awaiting approval`, actionNeeded: true, tone: "warn" },
  { key: "pending_bookings", label: t`Bookings awaiting approval`, actionNeeded: true, tone: "warn" },
  { key: "open_booking_issues", label: t`Booking issues`, actionNeeded: true, tone: "warn" },
  { key: "upcoming_events", label: t`Upcoming events`, actionNeeded: false, tone: "accent" },
  { key: "upcoming_bookings", label: t`Upcoming bookings`, actionNeeded: false, tone: "accent" },
  { key: "pending_prints", label: t`Pending prints`, actionNeeded: false, tone: "warn" },
  { key: "active_prints", label: t`Active prints`, actionNeeded: false, tone: "accent" },
  { key: "prints_awaiting_collection", label: t`Ready to collect`, actionNeeded: false, tone: "success" },
  { key: "maintenance_overdue", label: t`Maintenance overdue`, actionNeeded: true, tone: "danger" },
  { key: "warranty_expiring", label: t`Warranties expiring`, actionNeeded: true, tone: "warn" },
  { key: "stocktakes_awaiting_approval", label: t`Stocktakes awaiting approval`, actionNeeded: true, tone: "warn" },
  { key: "failed_emails", label: t`Failed emails`, actionNeeded: true, tone: "danger" },
];

export const MACHINE_TILE_KEYS = new Set<Tile["key"]>([
  "pending_prints",
  "active_prints",
  "prints_awaiting_collection",
  "warranty_expiring",
  "maintenance_overdue",
]);

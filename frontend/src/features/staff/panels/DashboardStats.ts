import { t } from "@lingui/core/macro";
import type { Dashboard } from "../../../generated/api";
// The decision-242 fields are hand-typed until the integrator regenerates the OpenAPI client.
export type DashboardCounts = Omit<Dashboard, "widgets" | "queue_tiles" | "outstanding_by_currency" | "next_up_events" | "attention">
  & { due_today_loans?: number; due_soon_loans?: number; true_low_stock?: number; in_repair?: number; payments_to_record?: number }
  // EB12/BK3 (open item A24): today's events, check-ins and bookings; rooms out of service this week.
  & { today_events?: number; today_check_ins?: number; today_bookings?: number; room_outages_week?: number };

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
  { key: "due_today_loans", label: t`Due back today`, actionNeeded: true, tone: "warn" },
  { key: "due_soon_loans", label: t`Due back soon`, actionNeeded: false, tone: "accent" },
  { key: "low_stock", label: t`Out of stock`, actionNeeded: true, tone: "danger" },
  { key: "true_low_stock", label: t`Low stock`, actionNeeded: true, tone: "warn" },
  { key: "in_repair", label: t`Items in repair`, actionNeeded: false, tone: "warn" },
  { key: "pending_payments", label: t`Pending payments`, actionNeeded: true, tone: "emphasis" },
  { key: "payments_to_record", label: t`Payments to record`, actionNeeded: true, tone: "warn" },
  { key: "pending_event_registrations", label: t`Registrations awaiting approval`, actionNeeded: true, tone: "warn" },
  { key: "pending_bookings", label: t`Bookings awaiting approval`, actionNeeded: true, tone: "warn" },
  { key: "open_booking_issues", label: t`Booking issues`, actionNeeded: true, tone: "warn" },
  { key: "today_events", label: t`Events today`, actionNeeded: false, tone: "accent" },
  { key: "today_check_ins", label: t`Checked in today`, actionNeeded: false, tone: "success" },
  { key: "today_bookings", label: t`Bookings today`, actionNeeded: false, tone: "accent" },
  { key: "room_outages_week", label: t`Rooms out of service this week`, actionNeeded: true, tone: "warn" },
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

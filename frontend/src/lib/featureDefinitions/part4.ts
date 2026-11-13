import { t } from "@lingui/core/macro";
import type { FeatureDefinition } from "./types";

// Slice 4 of 5 of `capabilities.FEATURE_DEFINITIONS`, in registry order; backend drift guards parse every file in this folder, so keep one literal per line.
export const FEATURE_DEFINITIONS_4: readonly FeatureDefinition[] = [
  // GAP2 M2: due and overdue reminders for item and room maintenance.
  { key: "inventory.maintenance_reminders", parent_module: null, label: t`Item maintenance reminders` },
  { key: "bookings.room_maintenance_reminders", parent_module: "bookings", label: t`Room maintenance reminders` },
  // L3 (#128, #132, #133): ID cards, programmes, event cards, tickets, wallet passes.
  { key: "membership.id_programmes", parent_module: "membership", label: t`ID programmes` },
  { key: "membership.wallet_passes", parent_module: "membership", label: t`Wallet passes for member cards` },
  { key: "events.id_cards", parent_module: "events", label: t`Event ID cards` },
  { key: "events.ticket_designs", parent_module: "events", label: t`Ticket designs` },
  { key: "events.wallet_passes", parent_module: "events", label: t`Wallet passes for event cards` },
  // L13 (#74, #128 C-12/C-13): a public Google Sheet as an import source.
  { key: "membership.import_sheets", parent_module: "membership", label: t`Member import from Google Sheets` },
  { key: "membership.id_programmes_import_sheets", parent_module: "membership", label: t`ID-programme import from Google Sheets` },
  // L6 (#69, #71, #128 C-20): paid ticketing v2 and venue fees.
  { key: "events.orders", parent_module: "events", label: t`Ticket orders` },
  { key: "events.seat_holds", parent_module: "events", label: t`Checkout seat holds` },
  { key: "events.addons", parent_module: "events", label: t`Ticket add-ons` },
  { key: "events.series_passes", parent_module: "events", label: t`Series passes` },
  { key: "events.transfers", parent_module: "events", label: t`Ticket transfers and type changes` },
  { key: "events.desk_collect", parent_module: "events", label: t`Collect payment at the desk` },
  { key: "events.refund_override", parent_module: "events", label: t`Per-event refund policy` },
  { key: "events.venue_fees", parent_module: "events", label: t`Venue fees for hosting` },
  // L18 (#94, #96, #128 C-14): donations, sponsors and calendar sync.
  { key: "finance.donations", parent_module: null, label: t`Donations` },
  { key: "finance.recurring_donations", parent_module: null, label: t`Recurring donations` },
  { key: "finance.sponsors", parent_module: null, label: t`Sponsors` },
  { key: "finance.tax_exempt_receipts", parent_module: null, label: t`Tax-exempt donation receipts` },
  { key: "charges.donations", parent_module: null, label: t`Track donation and sponsor money` },
  { key: "payments.donations", parent_module: "payments", label: t`Donation payments` },
  { key: "bookings.calendar_feed", parent_module: "bookings", label: t`Booking calendar feed` },
  { key: "events.calendar_feed", parent_module: "events", label: t`Event calendar feed` },
  { key: "events.shifts_feed", parent_module: "events", label: t`Shift calendar feed` },
  { key: "calendar.combined_feed", parent_module: null, label: t`Combined personal calendar` },
  { key: "events.public_feed", parent_module: "events", label: t`Public events calendar` },
  // L21a (#128 C-32..C-36): applications for any event, review stages, attendance, crew, check-in lists.
  { key: "events.applications", parent_module: "events", label: t`Applications for any event` },
  { key: "events.application_stages", parent_module: "events", label: t`Application review stages` },
  { key: "events.attendance_confirmation", parent_module: "events", label: t`Attendance confirmation` },
  { key: "events.crew", parent_module: "events", label: t`Event crew` },
  { key: "events.crew_claims", parent_module: "events", label: t`Crew expense claims` },
  { key: "events.checkin_lists", parent_module: "events", label: t`Custom check-in lists` },
  // L21b (X40, X50-X54, #128 C-37..C-39): finalists, prize payouts, fees, paid teams, saved views, gallery search.
  { key: "events.finalists", parent_module: "events", label: t`Finalists` },
  { key: "events.prize_payouts", parent_module: "events", label: t`Prize money and payouts` },
  { key: "events.entry_fees", parent_module: "events", label: t`Project entry fees` },
  { key: "events.paid_teams", parent_module: "events", label: t`Paid team registration` },
  { key: "events.saved_views", parent_module: "events", label: t`Saved views and exports for event lists` },
  { key: "events.gallery_search", parent_module: "events", label: t`Gallery search and awards` },
  // Hack-money (#180): prize splits and claims, refundable deposits, add-ons for accepted participants.
  { key: "events.prize_claims", parent_module: "events", label: t`Prize splits and winner claims` },
  { key: "events.deposits", parent_module: "events", label: t`Refundable hackathon deposits` },
  { key: "events.accepted_addons", parent_module: "events", label: t`Add-ons for accepted participants` },
  // r2-peoples-choice (#181 S3): an optional People's choice award voted on the public gallery.
  { key: "events.peoples_choice", parent_module: "events", label: t`People's choice award` },
  // L24 (#163A): price-drop refunds.
  { key: "charges.price_drop_refunds", parent_module: null, label: t`Price-drop refunds` },
  // L22 (#128 C-7, #129, #135, #137): the per-space shop.
  { key: "shop.online", parent_module: "shop", label: t`Online shop` },
  { key: "shop.guest_checkout", parent_module: "shop", label: t`Guest checkout` },
  { key: "shop.holds", parent_module: "shop", label: t`Stock holds at checkout` },
];

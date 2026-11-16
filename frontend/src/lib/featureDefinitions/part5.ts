import { t } from "@lingui/core/macro";
import type { FeatureDefinition } from "./types";

// Slice 5 of 5 of `capabilities.FEATURE_DEFINITIONS`, in registry order; backend drift guards parse every file in this folder, so keep one literal per line.
export const FEATURE_DEFINITIONS_5: readonly FeatureDefinition[] = [
  { key: "shop.member_prices", parent_module: "shop", label: t`Member prices` },
  { key: "shop.tax", parent_module: "shop", label: t`Shop tax classes` },
  { key: "shop.returns", parent_module: "shop", label: t`Returns and refunds` },
  { key: "shop.cash_up", parent_module: "shop", label: t`Cash-up` },
  { key: "shop.event_pickup", parent_module: "shop", label: t`Pickup at events` },
  { key: "shop.order_limits", parent_module: "shop", label: t`Per-order limits` },
  { key: "shop.public_stock", parent_module: "shop", label: t`Stock on the shop page` },
  { key: "shop.receipts", parent_module: "shop", label: t`Shop receipts` },
  { key: "shop.reorder", parent_module: "shop", label: t`Low-stock reorder` },
  { key: "shop.bundles", parent_module: "shop", label: t`Kit bundles` },
  { key: "shop.consumable_link", parent_module: "shop", label: t`Sell inventory consumables` },
  { key: "charges.shop", parent_module: "shop", label: t`Track shop sales` },
  { key: "payments.shop", parent_module: "shop", label: t`Online shop payments` },
  // L20 (#69, #128 C-31): the in-app help centre.
  { key: "platform.help_centre", parent_module: null, label: t`Help centre` },
  // Decision 223 (a, b, k): guest passes, day passes, minors, volunteer credit, the join funnel.
  { key: "membership.guest_passes", parent_module: "membership", label: t`Guest passes` },
  { key: "membership.day_passes", parent_module: "membership", label: t`Day passes` },
  { key: "events.guest_passes", parent_module: "events", label: t`Event guest passes` },
  { key: "membership.minors", parent_module: "membership", label: t`Minors and guardian consent` },
  { key: "membership.volunteer_credit", parent_module: "membership", label: t`Volunteer hours as membership credit` },
  { key: "membership.join_funnel", parent_module: "membership", label: t`Attendee join funnel` },
  { key: "bookings.organization_bookings", parent_module: "bookings", label: t`Organization bookings` },
  // Decision 223 (k), lane L3a: supervised sessions, the incident register (induction events were retired by decision 319).
  { key: "machines.supervised_sessions", parent_module: "machines", label: t`Supervised workshop sessions` },
  { key: "machines.certifications", parent_module: "machines", label: t`Certification gating` },
  { key: "machines.certification_reminders", parent_module: "machines", label: t`Certification reminders` },
  { key: "machines.induction_events", parent_module: "machines", label: t`Induction events` },
  { key: "safety.incidents", parent_module: null, label: t`Incident register` },
  // Parity O-B4: card numbering, title-change reissue, desk printing and staff ID cards.
  { key: "membership.card_numbering", parent_module: "membership", label: t`Card numbering schemes` },
  { key: "membership.title_card_reissue", parent_module: "membership", label: t`Reissue the card when the title changes` },
  { key: "membership.card_desk_print", parent_module: "membership", label: t`Desk card printing` },
  { key: "membership.staff_cards", parent_module: "membership", label: t`Staff ID cards` },
  { key: "membership.staff_cards_auto_issue", parent_module: "membership", label: t`Issue staff cards automatically` },
  // Decision 314(c): the background-eraser adapter for card photos.
  { key: "cards.photo_cutout", parent_module: "membership", label: t`Card photo background eraser` },
  // Parity E-B1/E-B2: the badge designer, desk badge printing and role badges.
  { key: "events.badge_designer", parent_module: "events", label: t`Badge designer` },
  { key: "events.badge_desk_print", parent_module: "events", label: t`Desk badge printing` },
  { key: "events.role_badges", parent_module: "events", label: t`Role badges` },
  // Parity E-B6 / E-B8 (UI: E-F5): refunds that cancel tickets, staff claims, sender identity, own legal pages.
  // Events R3 batches (B3-B7): team moderation, crew kinds, scores export, series invites, pay window, discovery, insights.
  { key: "events.team_moderation", parent_module: "events", label: t`Team handover and moderation` },
  { key: "events.crew_kinds", parent_module: "events", label: t`Crew kinds` },
  { key: "events.scores_export", parent_module: "events", label: t`Judging scores export` },
  { key: "events.series_invites", parent_module: "events", label: t`Series invite lists` },
  { key: "events.pay_window", parent_module: "events", label: t`24-hour payment window` },
  { key: "events.event_saved_views", parent_module: "events", label: t`Saved views for one event's guests` },
  { key: "events.discovery_filters", parent_module: "events", label: t`Discovery tag and organiser filters` },
  { key: "events.space_insights", parent_module: "events", label: t`Event insights` },
  { key: "events.refund_cancels_tickets", parent_module: "events", label: t`Refund can cancel tickets` },
  { key: "events.staff_claims", parent_module: "events", label: t`Staff expense claims` },
  { key: "email.sender_identity", parent_module: "email", label: t`Sender name and reply-to` },
  { key: "legal.space_pages", parent_module: null, label: t`Own privacy and terms pages` },
  { key: "display.anthias_push", parent_module: "presence", label: t`Send display screens to Anthias` },
];

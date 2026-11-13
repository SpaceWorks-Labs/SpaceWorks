import { t } from "@lingui/core/macro";
import { CalendarDays, CreditCard, DoorOpen, Package, Printer, ShoppingBag, type LucideIcon } from "lucide-react";

// The areas a makerspace switches on, in this app's own words. Every line is checked against
// docs/FEATURES.md, docs/MODULES.md and docs/release-0.12.0.md; the record rows are sample data.

export type AreaTone = "success" | "warn" | "info" | "neutral";
export type Area = {
  key: string; icon: LucideIcon; name: string; tagline: string; body: string; points: string[];
  record: { title: string; rows: { label: string; value: string; tone: AreaTone }[] };
  docsQuery: string;
};

export function hubAreas(): Area[] {
  return [
    { key: "inventory", icon: Package, name: t`Inventory`, tagline: t`Tools and parts, lent with proof.`,
      body: t`A public catalogue for each space, borrow requests that staff review, and a handover record for every loan.`,
      points: [t`Box QR scan and photo before anything leaves`, t`Return photo and remark before it comes back`,
        t`Kits, direct handouts and self-checkout when a space allows it`, t`Stocktakes, consumables and To-Buy lists`],
      record: { title: t`Shelf B · Hand tools`, rows: [
        { label: t`Cordless drill`, value: t`Available`, tone: "success" },
        { label: t`Hot air station`, value: t`Limited`, tone: "warn" },
        { label: t`Oscilloscope`, value: t`On loan until Friday`, tone: "info" },
      ] }, docsQuery: "inventory" },
    { key: "machines", icon: Printer, name: t`Machines`, tagline: t`Queues, not clipboards.`,
      body: t`Print and machine job requests, quotes and queues, with the training, maintenance and repairs behind them.`,
      points: [t`3D printers, spools and filament use`, t`Machine access given by a space manager`,
        t`Maintenance schedules that block a machine when overdue`, t`Repair work orders and metered sessions`],
      record: { title: t`Print queue · Printer 2`, rows: [
        { label: t`Bracket, PLA`, value: t`Printing`, tone: "info" },
        { label: t`Enclosure panel`, value: t`Quote sent`, tone: "warn" },
        { label: t`Laser cutter`, value: t`Certified members only`, tone: "neutral" },
      ] }, docsQuery: "machines" },
    { key: "events", icon: CalendarDays, name: t`Events`, tagline: t`From sign-up to certificate.`,
      body: t`One-off events and series with free or paid tickets, waitlists, applications and hackathons.`,
      points: [t`QR check-in at the door, even offline`, t`Approvals, waitlists and promo codes`,
        t`Attendance certificates and printable badges`, t`Mentors, volunteers, judges and crews`],
      record: { title: t`Intro to soldering · Saturday`, rows: [
        { label: t`Tickets`, value: t`18 of 24 taken`, tone: "success" },
        { label: t`Waitlist`, value: t`4 people`, tone: "warn" },
        { label: t`Check-in`, value: t`Opens at 13:30`, tone: "neutral" },
      ] }, docsQuery: "events" },
    { key: "bookings", icon: DoorOpen, name: t`Bookings`, tagline: t`Rooms and benches, booked properly.`,
      body: t`Bookable rooms and resources with public self-booking, recurring slots, approvals and arrival scans.`,
      points: [t`A readiness check before anyone submits`, t`Recurring and rescheduled bookings`,
        t`Printable passes and arrival scanning`, t`Organisation hours used before any charge`],
      record: { title: t`Meeting room · Thursday`, rows: [
        { label: t`09:00 – 11:00`, value: t`Booked`, tone: "info" },
        { label: t`11:00 – 13:00`, value: t`Free`, tone: "success" },
        { label: t`14:00 – 16:00`, value: t`Waiting for approval`, tone: "warn" },
      ] }, docsQuery: "bookings" },
    { key: "shop", icon: ShoppingBag, name: t`Shop`, tagline: t`Sell consumables without a second system.`,
      body: t`Consumables, kits and merch with variants, online checkout or pay at the desk, and a front-desk till.`,
      points: [t`Cash-ups at the end of the day`, t`Pickup codes and receipts`,
        t`Stock moves through the same inventory counts`, t`Every sale lands in the ledger`],
      record: { title: t`Front-desk till`, rows: [
        { label: t`PLA filament, 1 kg × 2`, value: t`In stock`, tone: "success" },
        { label: t`Starter electronics kit`, value: t`Last one`, tone: "warn" },
        { label: t`Order for pickup`, value: t`Ready`, tone: "info" },
      ] }, docsQuery: "shop" },
    { key: "money", icon: CreditCard, name: t`Memberships & payments`, tagline: t`Know who is a member and who owes what.`,
      body: t`Membership plans, renewals, cards and guest passes, and money owed tracked with or without an online gateway.`,
      points: [t`Offline payments recorded with a receipt`, t`Optional Stripe or Razorpay checkout`,
        t`Refunds only through approved refund cases`, t`Donations, sponsors and receipts for non-profits`],
      record: { title: t`Member account`, rows: [
        { label: t`Membership`, value: t`Active`, tone: "success" },
        { label: t`Workshop fee`, value: t`Paid at the desk`, tone: "info" },
        { label: t`Laser time`, value: t`Owed · pay link sent`, tone: "warn" },
      ] }, docsQuery: "membership" },
  ];
}

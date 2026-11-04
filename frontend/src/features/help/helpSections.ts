import type { HelpSection } from "./helpTypes";

// The guide's sections, in reading order. A section's folder under `src/help-content/<locale>/`
// has the same id. Staff sections follow ACTIONS, not role names: a custom role that holds the
// actions reads the same guide as the built-in role it resembles.
export const HELP_SECTIONS: readonly HelpSection[] = [
  { id: "member", title: "Members and visitors",
    summary: "Your account, borrowing, bookings, events, machine jobs and paying what you owe.",
    audience: { everyone: true } },
  { id: "organisation", title: "Organisations",
    summary: "Clubs, teams and companies that work with one or more spaces.",
    audience: { everyone: true } },
  { id: "space-manager", title: "Space Manager",
    summary: "Set up the space, choose what it runs, manage the team and keep the books straight.",
    audience: { actions: ["manage_makerspace"] } },
  { id: "inventory-manager", title: "Inventory Manager",
    summary: "Requests, handovers with evidence, QR codes, stocktakes and the shelves.",
    audience: { actions: ["edit_inventory", "accept_request", "reject_request", "manage_qr"], spaceManager: true } },
  { id: "handover", title: "Front desk and handover",
    summary: "Hand tools over and take them back, with the scans, photos and notes each one needs.",
    audience: { actions: ["issue_request", "issue_direct_loan", "return_request", "collect_service_request"], spaceManager: true } },
  { id: "machine-manager", title: "Machine Manager",
    summary: "Machines, job requests, quotes, sessions, certifications and maintenance.",
    audience: { actions: ["manage_machines", "manage_printing"], spaceManager: true } },
  { id: "technician", title: "Technician",
    summary: "Repair jobs assigned to you, scheduled maintenance and taking things out of service.",
    audience: { actions: ["work_repairs", "run_maintenance", "set_service_state"], spaceManager: true } },
  { id: "booking-manager", title: "Booking Manager",
    summary: "Rooms and resources, booking requests, arrivals and room upkeep.",
    audience: { actions: ["manage_bookings"], grants: ["bookings"], spaceManager: true } },
  { id: "event-manager", title: "Event Manager",
    summary: "Events, tickets, check-in, applications, hackathons, crews and sponsors.",
    audience: { actions: ["manage_events"], grants: ["events"], spaceManager: true } },
  { id: "finance", title: "Finance",
    summary: "Payments, offline receipts, refunds, the ledger, tax and price lists.",
    audience: { actions: ["view_finance", "record_payment"], spaceManager: true } },
  { id: "shop-manager", title: "Shop Manager",
    summary: "The shop: products, stock, online orders, the front-desk till and cash-ups.",
    audience: { actions: ["manage_shop", "sell_shop", "view_shop"], spaceManager: true } },
  { id: "superadmin", title: "Platform superadmin",
    summary: "Running every space on this server: spaces, people, modules, backups and moves.",
    audience: { platform: true } },
  { id: "host-operator", title: "Host operator",
    summary: "Installing, upgrading, backing up and securing the server Space Works runs on.",
    audience: { platform: true } },
];

export const SECTION_BY_ID: ReadonlyMap<string, HelpSection> = new Map(HELP_SECTIONS.map(section => [section.id, section]));

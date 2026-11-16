import { t } from "@lingui/core/macro";
import type { ModuleKey } from "../../../lib/retiredModules";

/** Curated off-state explanations; keys are checked against the same live registry as the cards. */
export function moduleWithout(): Record<ModuleKey, string> {
  const core = t`Always on: the catalogue, workflow, staff console, evidence, QR management and scanner protect every handover.`;
  return {
    public_inventory: core, request_workflow: core, staff_admin: core,
    evidence_uploads: core, qr_management: core, scanner: core,
    guest_handover: t`Front-desk handover routes are unavailable. Authorized staff can still issue and return from the console. Deposits that block issue are still checked.`,
    asset_units: t`Per-unit QR tracking disappears; stock counts stay.`,
    containers: t`The container hierarchy, moves and kit checklists disappear.`,
    bulk_import: t`The spreadsheet import tab disappears.`,
    stock_transfers: t`The stock transfer tab disappears.`,
    qr_print_batches: t`Batch label tools disappear; individual QR issuance remains available.`,
    stocktake: t`Stocktake sessions and variance screens disappear.`,
    machines: t`Machine screens, public machine feeds and usage sessions are unavailable.`,
    machine_service: t`Job requests and pickups are unavailable; the machine registry and usage sessions remain.`,
    devices: t`Device enrolment and adapter routes are unavailable.`,
    events: t`Event routes, public events and event machine-use pickers are unavailable; registrations stay saved.`,
    event_reimbursements: t`Event support, budget, award and expense-claim routes are unavailable; events continue. Reimbursements record money out, with no borrower charge.`,
    bookings: t`Resource booking routes and public booking pages are unavailable.`,
    membership: t`Community join queues, plans and membership cards are unavailable; the staff roster and role assignment remain.`,
    member_accounts: t`The space takes account-less requests with a name, phone and verified email. Staff sign-in remains available. Account-less self-checkout needs its own switch.`,
    presence: t`Check-in, the current roster and TV display routes are unavailable; history stays saved.`,
    notifications: t`The in-app inbox and module notification emitters stop; event notices are skipped.`,
    email: t`Space mail is recorded as skipped; platform account recovery and verification mail remain available.`,
    sms: t`No SMS notifications are sent. Sign-in phone codes are independent.`,
    whatsapp: t`No WhatsApp template notifications are sent.`,
    telegram: t`No Telegram alerts are sent; the saved bot token stays.`,
    slack: t`No Slack alerts are sent; the saved webhook stays.`,
    mattermost: t`No Mattermost alerts are sent; its configuration stays.`,
    discord: t`No Discord alerts are sent; its configuration stays.`,
    webhook: t`No signed notification webhooks are sent.`,
    reports: t`Report screens and exports are unavailable. Reports only read the ledger; they never raise charges.`,
    analytics: t`Analytics screens and routes are unavailable; the read-only database login stays saved.`,
    payments: t`No new online checkout starts. Money owed is still recorded, readable and settleable offline with a receipt.`,
    mobile: t`Native device grants and push are unavailable. The native payment sheet also needs online payments.`,
    shop: t`Shop routes are unavailable; orders and stock stay saved.`,
  };
}

/** Money belongs to the ledger even when the online payment module is absent. */
export function moduleMoney(key: ModuleKey): string {
  const money: Partial<Record<ModuleKey, string>> = {
    request_workflow: t`charges.loans records rental, deposits, late, damage and lost fees. Online checkout additionally needs payments.loans.`,
    guest_handover: t`Handover raises no charge itself; it checks any deposit required before issue.`,
    machines: t`charges.machines records a priced metered session when it stops. Online checkout additionally needs payments.machines, machine service and payments.`,
    machine_service: t`charges.machines records priced jobs at completion. Online checkout additionally needs payments.machines and payments.`,
    events: t`charges.events records ticket orders, paid registrations, add-ons, venue fees, team entry and refundable deposits. Online checkout additionally needs payments.events.`,
    event_reimbursements: t`Reimbursements record money out: support requests, budgets, awards and expense claims. They raise no incoming charge and use no charges switch.`,
    bookings: t`charges.bookings records resource and booked-time fees after included hours. Online checkout additionally needs payments.bookings.`,
    membership: t`charges.membership records dues, admission, terms opened by staff, renewals and guest passes. Online checkout additionally needs payments.membership.`,
    notifications: t`billing.reminders sends due-charge reminders to payers, including those who pay offline.`,
    reports: t`Reports read the ledger and raise no charges.`,
    payments: t`Online checkout only. The permanent ledger records money owed without this module; a debt without a provider is unclaimed and can be settled offline with a receipt.`,
    mobile: t`Native apps use the same area charge switches as the web. The native payment sheet needs the online rail.`,
    shop: t`charges.shop records every sale in one ledger payment. Catalogue and stock work free; sales require charging on. Cash sales need a receipt; online checkout additionally needs payments.shop.`,
  };
  return money[key] ?? t`This module raises no charge of its own.`;
}

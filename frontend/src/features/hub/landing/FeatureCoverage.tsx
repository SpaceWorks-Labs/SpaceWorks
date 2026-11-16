import { t } from "@lingui/core/macro";

/** All twelve module groups, plus the shared features that are not separate modules. */
function features() {
  return [
    { key: "inventory", name: t`Inventory & loans`, body: t`Public catalogue, QR labels, evidence, kits, direct handouts and returns.`,
      money: t`Works free. Optional rental, deposits, late, damage and lost fees: charges.loans.` },
    { key: "stocktake", name: t`Stocktake`, body: t`Scan shelves, compare counts and record stock adjustments and transfers.`,
      money: t`Works free. No fee for counting or moving stock.` },
    { key: "machines", name: t`Machines & printing`, body: t`Custom machine types, jobs, consumables, queues, access grants and metered sessions.`,
      money: t`Works free. Optional job, material and session fees: charges.machines.` },
    { key: "events", name: t`Events & hackathons`, body: t`Tickets, teams, submissions, judging, mentors, volunteers, badges and certificates.`,
      money: t`Works free. Optional tickets, add-ons, venue fees, team entry and deposits: charges.events.` },
    { key: "bookings", name: t`Bookings`, body: t`Rooms, benches and machine time, recurring slots, approvals, passes and included hours.`,
      money: t`Works free. Optional resource and time fees: charges.bookings.` },
    { key: "membership", name: t`Membership & ID cards`, body: t`Plans, renewals, waivers, guest passes, card design and public card validity checks.`,
      money: t`Works free. Optional dues, admission and guest-pass fees: charges.membership. Cards carry no fee.` },
    { key: "notifications", name: t`Notifications`, body: t`Personal inbox, email, SMS, WhatsApp, Telegram, Slack, Mattermost, Discord and signed webhooks.`,
      money: t`Works free. No member charge; external delivery providers may charge the operator.` },
    { key: "reports", name: t`Reports & analytics`, body: t`Scoped reports, CSV/XLSX exports, accessible charts with table fallbacks, public stats and platform totals. Metabase analytics is optional and off by default.`,
      money: t`Works free. No fee for reports or exports.` },
    { key: "payments", name: t`Money & receipts`, body: t`One ledger for debts, offline receipts, tax, expenses and staff-approved refunds.`,
      money: t`Works free. Each area chooses its own charges switch; online payments are optional.` },
    { key: "mobile", name: t`Mobile apps`, body: t`Native Android and iOS sessions, push notifications and the optional payment sheet.`,
      money: t`Works free. Uses the same area charges switches and optional online rail as the web.` },
    { key: "devices", name: t`Connected devices`, body: t`Signed printer and label-device connections, adapters, telemetry and camera records.`,
      money: t`Works free. Devices add no separate fee; priced machine work uses charges.machines.` },
    { key: "shop", name: t`Shop`, body: t`Consumables, kits and merch, stock holds, pickup, a front-desk till and cash-ups.`,
      money: t`Works free. Catalogue and stock need no fee. Selling requires charges.shop; offline cash with a receipt works, online payments are optional.` },
    { key: "donations", name: t`Donations & sponsors`, body: t`Campaigns, sponsor recognition, recurring pledges and optional tax-exempt receipts.`,
      money: t`Works free. Campaigns and recognition need no fee; accepting money requires charges.donations.` },
    { key: "presence", name: t`Presence & public TV`, body: t`Member and guest check-in, privacy controls, opening hours and paired workshop screens.`,
      money: t`Works free. No fee for check-in or the public display.` },
    { key: "people", name: t`Accounts, organizations & profiles`, body: t`One account per person, fixed staff roles, organization links and opt-in public profiles.`,
      money: t`Works free. Accounts, staff access and publishing profiles have no fee.` },
    { key: "pages", name: t`Public pages`, body: t`Publish space, organization, event and booking websites. The public space page includes Here now, Machines now and an events calendar. The product landing can be switched off; Features stays available.`,
      money: t`Works free. No fee for publishing a page.` },
    { key: "repairs", name: t`Repairs & maintenance`, body: t`Issue reports, repairs, work orders, quotes and parts, warranty and a safety incident register. One schedule combines bookings, events, staff shifts, machine jobs and maintenance.`,
      money: t`Works free. Repair expenses are recorded; optional borrower damage fees use charges.loans.` },
    { key: "data", name: t`API access, backup & portability`, body: t`Scoped API clients, full data exports, platform backups, single-space restore points and encrypted exports to move a space onto its own server.`,
      money: t`Works free. No member fee for API access, backups or taking your data with you.` },
    { key: "security", name: t`Security, privacy & help`, body: t`Ten built-in roles scoped by makerspace and action, staff second factors and a separate superadmin control plane. Append-only audit logs and immutable photo metadata, remarks and scans survive photo retention expiry. Live staff queues use Server-Sent Events; search tolerates typos. Request IDs connect logs and Prometheus is token-protected.`,
      money: t`Works free. Security and help have no paid upgrade.` },
  ];
}

export function FeatureCoverage() {
  return <div className="mt-16" role="region" aria-labelledby="feature-coverage-title">
    <h3 id="feature-coverage-title" className="font-display text-3xl font-extrabold tracking-tight text-ink">{t`Every area can run free`}</h3>
    <p className="mt-4 max-w-3xl text-muted">{t`Turn off charges.enabled for a fully free space. Otherwise, choose charges separately for each area. Online payments are optional: Stripe or Razorpay can be added, and offline payments are recorded with a receipt.`}</p>
    <ul className="mt-8 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
      {features().map(feature => <li key={feature.key} data-feature-area={feature.key} className="grid content-start gap-2">
        <h4 className="font-semibold text-ink">{feature.name}</h4>
        <p className="text-sm leading-6 text-muted">{feature.body}</p>
        <p className="text-sm leading-6 text-ink">{feature.money}</p>
      </li>)}
    </ul>
  </div>;
}

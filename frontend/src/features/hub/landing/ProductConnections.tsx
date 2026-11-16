import { t } from "@lingui/core/macro";
import { Link } from "react-router-dom";

/** Shared by the product landing and /features; these relationships span module definitions. */
export function ProductConnections() {
  const connections = [
    t`Membership and mobile apps require member accounts. Event reimbursements require events. These are installation requirements.`,
    t`Events can link tool loans, machine jobs and venue bookings. Booking decisions stay with the booking workflow. Machine time can be booked, and membership plans can include booking hours.`,
    t`Shop orders can be picked up at an event. Presence can connect an event visit to an equipment-use window. These links appear only while both areas are enabled; switching one off leaves the other working.`,
    t`Loans, machine work, bookings, events, membership, shop sales and gifts write to one charges ledger. Online checkout is an optional addition. Notifications fan out to email and the configured chat, SMS and webhook channels.`,
    t`The public TV reads only what visitors may already see: presence for Here now, machines for Machines now and events for the calendar. A disabled source module hides its section.`,
  ];
  const integrations: [string, string][] = [
    [t`Phone apps`, t`Branded Android and iOS apps for members and staff, with push notifications and staff access through a verified step-up. Both are available from GitHub Releases.`],
    [t`Connected machines`, t`Printers and label printers on your network enrol with a signed device identity. One adapter API handles status, commands, jobs, access, kiosk checkout, cameras and telemetry; jobs report through the normal workflow.`],
    [t`Messages`, t`Email, an in-app inbox, Telegram, Slack, Mattermost, Discord, signed webhooks, SMS through Twilio and WhatsApp through Twilio or Meta, routed to the rooms and people you choose.`],
    [t`Sign-in`, t`Password, Google, Apple, GitHub, your own OIDC provider and phone codes. Spaces can also take walk-in requests without member accounts.`],
    [t`Payments`, t`Stripe and Razorpay checkout, UPI QR codes, offline receipts and India GST invoices.`],
    [t`Calendars`, t`Google Calendar, Apple Calendar and Outlook: Add to Google Calendar, ICS downloads on event and booking confirmations, and subscribable feeds for events, bookings and maintenance.`],
    [t`Your own systems`, t`OpenAPI, Swagger and ReDoc, signed webhooks, scoped and signed API clients including space-to-space clients, personal access tokens, OAuth app connections and CSV/XLSX import and export.`],
    [t`Storage`, t`Any S3-compatible bucket: the bundled Silo store, AWS S3, Cloudflare R2 or MinIO.`],
  ];
  return <>
    <section className="mt-16" aria-labelledby="product-connections-title">
      <h3 id="product-connections-title" className="title-section">{t`How modules connect`}</h3>
      <ul className="mt-5 grid gap-4 text-muted">{connections.map(line => <li key={line}>{line}</li>)}</ul>
    </section>
    <section className="mt-16" aria-labelledby="product-integrations-title">
      <h3 id="product-integrations-title" className="title-section">{t`Integrations`}</h3>
      <p className="mt-4 text-muted">{t`Every integration is optional and configured per makerspace. Leave one out and the rest keeps working.`}</p>
      <dl className="mt-6 grid gap-6 sm:grid-cols-2">{integrations.map(([name, description]) => <div key={name} className="min-w-0">
        <dt className="font-semibold text-ink">{name}</dt><dd className="mt-2 text-sm leading-6 text-muted">{description}</dd>
      </div>)}</dl>
      <Link to="/docs/api-guide" className="sw-hub-inline-link mt-5 inline-block">{t`Connect your own systems`}</Link>
    </section>
  </>;
}

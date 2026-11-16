import { t } from "@lingui/core/macro";
import { CalendarCheck, CalendarDays, Receipt } from "lucide-react";
import type { CataloguePart } from "./types";

/** Events and Bookings groups. */
export const eventsAndBookings = (): CataloguePart => ({
  events: { icon: CalendarDays, value: t`From sign-up to certificate.`,
    what: t`One-off and recurring events, approvals, waitlists, ticket types, invitations and promo codes. QR door check-in supports offline rosters and PIN stations. Gather feedback, issue attendance certificates and printable badges, and publish member calendar feeds, hackathon programmes and project galleries. Curated public websites, email campaigns, draft cloning and scoped reports support the full event lifecycle.`,
    roles: [t`Event organizers`, t`Door staff`, t`Attendees`, t`Speakers`],
    
    
    
    integrations: [t`Online payments`, t`Wallet passes`, t`Calendar feeds`, t`Badge and certificate printing`, t`Email and chat alerts`],
    newIn: [t`Certificates from Card Studio`, t`Badge designer with role variants`] },
  event_reimbursements: { icon: Receipt, value: t`Pay organizers and volunteers back for event costs.`,
    what: t`Event support requests, finite budgets, awards and expense claims with receipts, manager review and payment recorded against the event.`,
    roles: [t`Event organizers`, t`Space managers`], 
    integrations: [t`Receipt uploads`] },
  bookings: { icon: CalendarCheck, value: t`Rooms, benches and equipment, booked properly.`,
    what: t`Bookable resources with public self-booking, one-off and recurring slots, rescheduling, arrival scans, printable passes and an approval queue. Publish curated booking websites and calendar feeds, send email campaigns, clone drafts and read scoped reports.`,
    roles: [t`Members`, t`Organizations`, t`Space managers`],
    
    
    integrations: [t`Online payments`, t`Calendar feeds (ICS)`, t`Embeddable page`, t`Pass printing`] },
});

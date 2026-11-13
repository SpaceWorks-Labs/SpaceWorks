import { t } from "@lingui/core/macro";
import { CalendarCheck, CalendarDays, Receipt } from "lucide-react";
import type { CataloguePart } from "./types";

/** Events and Bookings groups. */
export const eventsAndBookings = (): CataloguePart => ({
  events: { icon: CalendarDays, value: t`From sign-up to certificate.`,
    what: t`Free or paid tickets, promo codes, offline check-in, badges with role variants, certificates for attendees and speakers, hackathon programmes and a project gallery.`,
    roles: [t`Event organizers`, t`Door staff`, t`Attendees`, t`Speakers`],
    
    
    
    integrations: [t`Online payments`, t`Wallet passes`, t`Calendar feeds`, t`Badge and certificate printing`, t`Email and chat alerts`],
    newIn: [t`Certificates from Card Studio`, t`Badge designer with role variants`] },
  event_reimbursements: { icon: Receipt, value: t`Pay organizers and volunteers back for event costs.`,
    what: t`Claims with receipts, review by a manager and payment recorded against the event.`,
    roles: [t`Event organizers`, t`Space managers`], 
    integrations: [t`Receipt uploads`] },
  bookings: { icon: CalendarCheck, value: t`Rooms, benches and equipment, booked properly.`,
    what: t`One-off and recurring bookings with rules, printable passes, check-in, calendar feeds and an embeddable public page.`,
    roles: [t`Members`, t`Organizations`, t`Space managers`],
    
    
    integrations: [t`Online payments`, t`Calendar feeds (ICS)`, t`Embeddable page`, t`Pass printing`] },
});

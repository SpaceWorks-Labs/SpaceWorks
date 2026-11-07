import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Modal } from "../../components/ui";
import type { PublicEventDetail } from "../events/eventTicketTypes";
import { EventRegistrationForm } from "./EventRegistrationForm";
import { tenantPath, useOptionalTenant } from "../../lib/tenant";
import { useChargesOn } from "../../lib/charges";
import { TicketShopEntry } from "../events/ticketing/TicketShopEntry";

export function EventRegistrationEntry({ event, makerspaceSlug, organisation, ordersEnabled = false }: { event: PublicEventDetail; makerspaceSlug: string; organisation: string; ordersEnabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const chargesOn = useChargesOn("events", makerspaceSlug);
  // Release 2 L6: spaces selling ticket orders get the order shop for open, no-approval events. With event
  // charges off (#184) the same shop runs free: no prices, and the order settles without a payment step.
  const orderable = ordersEnabled && !event.registration_requires_approval
    && ["members", "accounts"].includes(event.registration_audience ?? "members");
  const mode = useOptionalTenant()?.mode ?? "central";
  const paid = chargesOn && (Number(event.payment_amount) > 0 || Boolean(event.ticket_types?.some(ticket => Number(ticket.amount) > 0)));
  const label = event.registration_requires_approval ? "Apply" : event.availability === "Full" ? "Join waitlist" : "Register";
  const form = <EventRegistrationForm makerspaceSlug={makerspaceSlug} publicToken={event.public_token}
    waitlist={event.availability === "Full"} approvalRequired={event.registration_requires_approval}
    customForm={event.custom_form} audience={event.registration_audience} tickets={event.ticket_types}
    ticketRequired={event.ticket_selection_required} promoEnabled={event.promo_codes_enabled} currency={event.currency} organisation={organisation}
    paymentsHref={paid ? tenantPath(mode, makerspaceSlug, "member/payments") : ""} />;
  if (orderable) return <TicketShopEntry makerspaceSlug={makerspaceSlug} publicToken={event.public_token} free={!chargesOn} />;
  if ((event.ticket_selection_required && !event.ticket_types?.length) || (!event.custom_form && !event.ticket_types?.length && !event.promo_codes_enabled && event.registration_audience !== "invite")) return form;
  return <><button hidden={open} className="desk-button-brand w-full" type="button" onClick={() => setOpen(true)}>{label}</button>
    <Modal open={open} onClose={() => setOpen(false)} title={event.title} footer={<button className="desk-button" type="button" onClick={() => setOpen(false)}>{t`Close form`}</button>}>
      {form}
    </Modal></>;
}

import { EventDisclosure } from "../EventDisclosure";
import { EventAddonsEditor } from "./EventAddonsEditor";
import { EventOrdersList } from "./EventOrdersList";
import { EventRefundPolicyForm } from "./EventRefundPolicyForm";
import { EventSalesRules } from "./EventSalesRules";
import { EventVenueFeeForm } from "./EventVenueFeeForm";
import { TicketOrderOptions } from "./TicketOrderOptions";

/** Paid ticketing v2 in the event drawer's Tickets section. Each tool shows only while its switch is on;
 * money policy (refund override, venue fee) only for the space's event managers. */
export function EventOrderTools({ eventId, features, manager, disabled = false }: {
  eventId: number; features: string[]; manager: boolean; disabled?: boolean;
}) {
  const on = (key: string) => features.includes(key);
  if (!on("events.orders") && !on("events.refund_override") && !on("events.venue_fees")) return null;
  return <section className="grid gap-4" aria-label="Ticket orders and money">
    {on("events.orders") ? <>
      <EventOrdersList eventId={eventId} />
      <EventDisclosure title="Ticket order options"><TicketOrderOptions eventId={eventId} disabled={disabled} /></EventDisclosure>
      <EventDisclosure title="Sales rules"><EventSalesRules eventId={eventId} transfers={on("events.transfers")} disabled={disabled} /></EventDisclosure>
    </> : null}
    {on("events.addons") ? <EventDisclosure title="Add-ons"><EventAddonsEditor eventId={eventId} disabled={disabled} /></EventDisclosure> : null}
    {manager && on("events.refund_override") ? <EventDisclosure title="Refund policy"><EventRefundPolicyForm eventId={eventId} disabled={disabled} /></EventDisclosure> : null}
    {manager && on("events.venue_fees") ? <EventDisclosure title="Venue fee"><EventVenueFeeForm eventId={eventId} disabled={disabled} /></EventDisclosure> : null}
  </section>;
}

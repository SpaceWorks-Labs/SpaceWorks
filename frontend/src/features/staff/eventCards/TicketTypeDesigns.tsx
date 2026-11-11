import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CardDesigner } from "../../../components/card-designer/CardDesigner";
import type { CardDesign } from "../../../components/card-designer/cardTypes";
import { ErrorBlock, Field, Skeleton } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { eventOptions, type StaffTicket } from "../eventTicketingApi";

/**
 * Ticket design per ticket type (parity D17). "Every ticket type" edits the event's design; choosing a type
 * edits (and on first use creates, from the event pass) that type's own design, which wins over the event's
 * for its holders. Resolution on the server: ticket type, then event, then the organisation default.
 */
export function TicketTypeDesigns({ eventId, eventDesign, ticketTypesOn }: {
  eventId: number; eventDesign: CardDesign; ticketTypesOn: boolean;
}) {
  const [typeId, setTypeId] = useState("");
  const types = useQuery({ queryKey: ["event", eventId, "ticket-types", "all"], enabled: ticketTypesOn, retry: false,
    queryFn: () => eventOptions<StaffTicket>(`/admin/events/${eventId}/ticket-types/`) });
  const typed = useQuery({ queryKey: ["event-card-designs", eventId, "ticket-type", typeId], enabled: Boolean(typeId),
    queryFn: () => staffRequest<Partial<Record<"event_card" | "event_ticket", CardDesign>>>(`/admin/events/${eventId}/card-designs?ticket_type=${typeId}`) });
  const rows = types.data ?? [];
  const chosen = rows.find(row => String(row.id) === typeId);
  const design = typeId ? typed.data?.event_ticket : eventDesign;
  const typeName = chosen?.name ?? t`this ticket type`;
  return <div className="grid gap-3">
    {ticketTypesOn && rows.length ? <Field label={t`Design for`}
      hint={typeId ? t`Holders of ${typeName} get this design instead of the event's.` : t`The event's design, used by every ticket type without its own.`}>
      <select className="desk-input max-w-sm" value={typeId} onChange={event => setTypeId(event.target.value)}>
        <option value="">{t`Every ticket type`}</option>
        {rows.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></Field> : null}
    {typeId && typed.isLoading ? <Skeleton className="h-40 w-full" /> : null}
    {typeId && typed.isError ? <ErrorBlock error={typed.error} resource={t`ticket design`} /> : null}
    {design ? <CardDesigner key={design.id} designId={design.id} canEdit={design.can_edit}
      title={chosen ? t`Ticket design: ${chosen.name}` : t`Ticket design`} /> : null}
  </div>;
}

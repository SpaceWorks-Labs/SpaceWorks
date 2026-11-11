import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import type { Paginated } from "../eventsApiTypes";

import { opsStatusLabel } from "../opsPresentation";
import type { StaffTicket } from "../eventTicketingApi";
import type { RegistrationFilters } from "../eventsRegistrationApi";

const STATUSES = ["pending_approval", "waitlisted", "registered", "attended", "cancelled", "rejected"] as const;

/**
 * EB5: find waitlisted and pending guests, one ticket type's holders, or one person, without
 * paging through the whole roster. The server applies every filter (decision 242).
 */
export function RegistrationFiltersBar({ value, onChange, tickets }: {
  value: RegistrationFilters; onChange: (next: RegistrationFilters) => void; tickets: StaffTicket[];
}) {
  const active = Boolean(value.status || value.ticket_type || value.q);
  return <div className="mb-4 grid min-w-0 gap-3 sm:grid-cols-3" role="group" aria-label={t`Filter registrations`}>
    <label className="grid min-w-0 gap-1 text-sm font-semibold">{t`Search guests`}
      <input className="desk-input" type="search" value={value.q ?? ""} onChange={event => onChange({ ...value, q: event.target.value })} /></label>
    <label className="grid min-w-0 gap-1 text-sm font-semibold">{t`Status`}
      <select className="desk-input max-w-full" value={value.status ?? ""} onChange={event => onChange({ ...value, status: event.target.value })}>
        <option value="">{t`Any status`}</option>
        {STATUSES.map(status => <option key={status} value={status}>{opsStatusLabel(status)}</option>)}
      </select></label>
    {tickets.length ? <label className="grid min-w-0 gap-1 text-sm font-semibold">{t`Ticket`}
      <select className="desk-input max-w-full" value={value.ticket_type ?? ""} onChange={event => onChange({ ...value, ticket_type: event.target.value })}>
        <option value="">{t`Any ticket`}</option>
        {tickets.map(ticket => <option key={ticket.id} value={String(ticket.id)}>{ticket.name}</option>)}
      </select></label> : null}
    {tickets.length ? <label className="flex min-h-11 items-center gap-3 self-end text-sm">
      <input type="checkbox" className="h-5 w-5 accent-accent" checked={value.group === "ticket_type"}
        onChange={event => onChange({ ...value, group: event.target.checked ? "ticket_type" : "" })} />{t`Sort by ticket`}</label> : null}
    {active ? <button type="button" className="desk-button w-fit self-end" onClick={() => onChange({})}>{t`Clear filters`}</button> : null}
  </div>;
}

/** The filter bar with this event's ticket types loaded (readable with manage_registrations, EB4). */
export function TicketedFiltersBar({ eventId, value, onChange }: {
  eventId: number; value: RegistrationFilters; onChange: (next: RegistrationFilters) => void;
}) {
  const tickets = useQuery({ queryKey: ["event", eventId, "ticket-types", "roster"], retry: false,
    queryFn: () => staffRequest<Paginated<StaffTicket>>(`/admin/events/${eventId}/ticket-types/?page=1`) });
  return <RegistrationFiltersBar value={value} onChange={onChange} tickets={tickets.data?.results ?? []} />;
}

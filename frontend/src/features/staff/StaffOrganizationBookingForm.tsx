import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { staffRequest } from "../../lib/api";
import { bookingKeys, type BookableSpace, type Booking } from "./bookingsApi";
import { StaffBookingAvailability } from "./StaffBookingAvailability";
import { OrganizationHoursBankEditor } from "./OrganizationHoursBankEditor";

type OrganizationChoice = { organization_id: number; name: string; contacts: { member_id: number; name: string }[] };

function iso(local: string) {
  const date = new Date(local);
  return local && !Number.isNaN(date.getTime()) ? date.toISOString() : "";
}

/**
 * Decision 223 P2 (`bookings.organization_bookings`): staff book a space for an organization's
 * partner event. The booking is made for one of the organization's members at this space (the
 * contact the room charge is recorded against) and shows the organization's name.
 */
export function StaffOrganizationBookingForm({ makerspaceId, space }: { makerspaceId: number; space: BookableSpace }) {
  const client = useQueryClient();
  const choices = useQuery({ queryKey: ["booking-space", space.id, "organization-choices"], retry: false,
    queryFn: () => staffRequest<OrganizationChoice[]>(`/admin/spaces/${space.id}/organization-bookings/choices/`) });
  const [organizationId, setOrganizationId] = useState(0);
  const [contactId, setContactId] = useState(0);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [note, setNote] = useState("");
  const create = useMutation({
    mutationFn: (body: { organization_id: number; contact_member_id: number; starts_at: string; ends_at: string; note: string }) =>
      staffRequest<Booking>(`/admin/spaces/${space.id}/organization-bookings/`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: async () => {
      setOrganizationId(0); setContactId(0); setNote("");
      await Promise.all([
        client.invalidateQueries({ queryKey: bookingKeys.bookings(space.id) }),
        client.invalidateQueries({ queryKey: bookingKeys.availability(space.id) }),
        client.invalidateQueries({ queryKey: bookingKeys.spaces(makerspaceId) }),
        client.invalidateQueries({ queryKey: ["booking-queue", makerspaceId] }),
        client.invalidateQueries({ queryKey: ["public-space-availability"] }),
      ]);
    },
  });
  const organization = choices.data?.find(row => row.organization_id === organizationId);
  const startsAt = iso(start);
  const endsAt = iso(end);
  const ready = Boolean(organizationId && contactId && startsAt && endsAt && endsAt > startsAt);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (ready) create.mutate({ organization_id: organizationId, contact_member_id: contactId, starts_at: startsAt, ends_at: endsAt, note: note.trim() });
  };
  return <form className="mb-4 grid gap-3 rounded-lg border border-line p-3" onSubmit={submit}>
    <h4 className="title-section">{t`Book for an organization`}</h4>
    <p className="text-xs text-muted">{t`For a partner organization's event. The room charge, if any, is recorded against the contact you choose.`}</p>
    {choices.isPending ? <p role="status" className="text-sm text-muted">{t`Loading organizations…`}</p> : null}
    {choices.isError ? <p role="alert" className="text-sm text-danger">{t`Organizations are unavailable. Check that organization bookings are switched on.`}</p> : null}
    {choices.isSuccess && !choices.data.length ? <p className="text-sm">{t`No organization is linked to this space yet.`}</p> : null}
    {choices.data?.length ? <fieldset className="grid gap-3 sm:grid-cols-2" disabled={create.isPending}>
      <label className="grid gap-1 text-sm">{t`Organization`}
        <select className="desk-input" required value={organizationId} onChange={change => { setOrganizationId(Number(change.target.value)); setContactId(0); }}>
          <option value={0}>{t`Select an organization`}</option>
          {choices.data.map(row => <option key={row.organization_id} value={row.organization_id}>{row.name}</option>)}
        </select></label>
      <label className="grid gap-1 text-sm">{t`Contact`}
        <select className="desk-input" required value={contactId} disabled={!organization} onChange={change => setContactId(Number(change.target.value))}>
          <option value={0}>{organization && !organization.contacts.length ? t`No member of this organization belongs to the space` : t`Select a contact`}</option>
          {organization?.contacts.map(row => <option key={row.member_id} value={row.member_id}>{row.name}</option>)}
        </select></label>
      <label className="grid gap-1 text-sm">{t`Starts (your local time)`}<input className="desk-input w-full min-w-0" type="datetime-local" required value={start} onChange={change => setStart(change.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Ends (your local time)`}<input className="desk-input w-full min-w-0" type="datetime-local" required value={end} onChange={change => setEnd(change.target.value)} /></label>
      <label className="grid gap-1 text-sm sm:col-span-2">{t`Staff note`}<textarea className="desk-input" maxLength={5000} value={note} onChange={change => setNote(change.target.value)} /></label>
    </fieldset> : null}
    {organizationId ? <OrganizationHoursBankEditor makerspaceId={makerspaceId} organizationId={organizationId} /> : null}
    <StaffBookingAvailability spaceId={space.id} start={start} end={end} />
    {create.error ? <p role="alert" className="text-sm text-danger">{create.error.message}</p> : null}
    {create.isSuccess ? <p role="status" className="text-sm text-success-ink">{create.data.status === "pending" ? t`Booking requested; it awaits approval.` : t`Booking created.`}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!ready || create.isPending}>{create.isPending ? t`Booking…` : t`Create organization booking`}</button>
  </form>;
}

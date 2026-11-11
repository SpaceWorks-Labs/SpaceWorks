import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { memberRequest } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import type { EventHistory } from "../events/eventHistoryApi";
import type { MemberBooking } from "../bookings/MyBookings";
import { EquipmentPurpose, type EquipmentPurposeValue } from "./EquipmentPurpose";
import { PendingIntake, type RequestFields, type SelfBody, type SelfResult } from "./contextualIntake";
import { KitChoice } from "./KitChoice";
import type { SafeKit } from "./equipmentKitsApi";
import { useContextualIntent } from "./useContextualIntent";
import { PagePager } from "../../components/ui";

type BookingPage = { results: MemberBooking[]; count: number; next: string | null };
export function ContextualRequest({ scope, slug, makerspaceId, eventsEnabled, bookingsEnabled, fields, canSubmit, onComplete, onSuccess, onLock, onDenied, pendingOwner, admitted }: {
  scope: string; slug: string; makerspaceId: number; eventsEnabled: boolean; bookingsEnabled: boolean; fields: RequestFields; canSubmit: boolean; onComplete?: (result: SelfResult) => void; onSuccess?: (result: SelfResult, scope: string) => void; onLock: () => void; onDenied: () => void; pendingOwner: PendingIntake<SelfBody>; admitted: () => boolean;
}) {
  const client = useQueryClient();
  const [denied, setDenied] = useState(false);
  const [value, setValue] = useState<EquipmentPurposeValue>({ eventRegistrationId: null, bookingToken: null });
  const [bookingPage, setBookingPage] = useState(1);
  const [kit, setKit] = useState<SafeKit | null>(null);
  const events = useQuery({ queryKey: ["contextual-intake", scope, "events"], enabled: eventsEnabled && !denied, retry: false,
    queryFn: () => memberRequest<EventHistory>(`/member/makerspaces/${makerspaceId}/event-history/`) });
  const bookings = useQuery({ queryKey: ["contextual-intake", scope, "bookings", bookingPage], enabled: bookingsEnabled && !denied, retry: false,
    queryFn: () => memberRequest<BookingPage>(`/public/${encodeURIComponent(slug)}/my-bookings/?period=upcoming&page=${bookingPage}`) });
  const conceal = () => { setDenied(true); setValue({ eventRegistrationId: null, bookingToken: null }); client.removeQueries({ queryKey: ["contextual-intake", scope] }); };
  const intent = useContextualIntent(scope, slug, pendingOwner, conceal, onDenied, admitted, onSuccess);
  const busy = intent.state === "sending" || intent.state === "uncertain";
  const retryAllowed = Boolean(intent.pendingBody) && (!intent.pendingBody?.event_registration_id || eventsEnabled) && (!intent.pendingBody?.booking_token || bookingsEnabled);
  const eventChoices = events.isError ? [] : (events.data?.registrations ?? []).filter(row => ["registered", "attended"].includes(row.status))
    .map(row => ({ registrationId: row.registration_id, label: row.event.title }));
  const bookingChoices = bookings.isError ? [] : (bookings.data?.results ?? []).filter(row => row.status === "confirmed")
    .map(row => ({ token: row.public_token, label: `${row.space_name} - ${formatDateTime(row.starts_at)}` }));
  const selectedAllowed = (!value.eventRegistrationId || eventsEnabled && !events.isError && eventChoices.some(row => row.registrationId === value.eventRegistrationId))
    && (!value.bookingToken || bookingsEnabled && !bookings.isError && bookingChoices.some(row => row.token === value.bookingToken));
  async function finish(result: Promise<SelfResult | undefined>) { const value = await result; if (value && !onSuccess) onComplete?.(value); }
  const selectedFields: RequestFields = kit ? { requested_for: fields.requested_for, website: fields.website, pickup_from: fields.pickup_from, pickup_until: fields.pickup_until, waitlist_entry_id: fields.waitlist_entry_id, kit: { id: kit.id, version: kit.version } } : fields;
  if (denied) return <p className="text-sm text-muted" role="status">{t`This request is unavailable for your access.`}</p>;
  return <section className="grid gap-3" data-replay-block>
    <EquipmentPurpose value={value} onChange={setValue} events={eventChoices} bookings={bookingChoices} eventsEnabled={eventsEnabled} bookingsEnabled={bookingsEnabled} disabled={busy} />
    <KitChoice scope={scope} slug={slug} value={kit} onChange={setKit} disabled={busy} />
    {events.isError || bookings.isError ? <p className="text-sm text-muted" role="status">{t`Some choices are unavailable. You can still make an ordinary request.`}</p> : null}
    {bookingsEnabled && bookings.data ? <PagePager page={bookingPage} setPage={next => { setValue(v => ({ ...v, bookingToken: null })); setBookingPage(next); }} next={bookings.data.next} disabled={busy} /> : null}
    {intent.error ? <p className="text-sm text-danger" role="alert">{intent.state === "uncertain" ? t`The request outcome may be unknown. Review your request history or retry the same request.` : t`Check your request and try again.`}</p> : null}
    {intent.state === "uncertain" ? <button type="button" className="desk-button w-fit" disabled={!retryAllowed} onClick={() => void finish(intent.retry())}>{t`Retry the same request`}</button>
      : <button type="button" className="desk-button-primary w-fit" disabled={!canSubmit || (!kit && !fields.items?.length) || busy || !selectedAllowed} onClick={() => { if (!admitted()) { conceal(); return; } onLock(); void finish(intent.begin(selectedFields, value.eventRegistrationId, value.bookingToken)); }}>{intent.state === "sending" ? t`Submitting request…` : t`Submit equipment request`}</button>}
  </section>;
}

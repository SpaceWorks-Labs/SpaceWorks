import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { staffRequest } from "../../../lib/api";
import { formatDateTime } from "../../../lib/format";
import { opsStatusLabel } from "../opsPresentation";
import type { Domain } from "./api";
import { EventPanelPager } from "../EventPanelPager";
import { LogoLoader } from "../../../components/LogoLoader";

type Choice = { id: number; title?: string; name?: string; space_name?: string; starts_at?: string };
type Page = { count?: number; results: Choice[]; next: string | null; previous: string | null };
function EventChoices({ tenant, scope, onSelect }: { tenant: number; scope: string; onSelect: (id: number) => void }) {
  const [page, setPage] = useState(1);
  const list = useQuery({ queryKey: ["loan-context-choices", scope, "event", page],
    queryFn: () => staffRequest<Page>(`/admin/accessible-events/?page=${page}&makerspace_id=${tenant}`), retry: false });
  return <div className="grid gap-2">{list.isPending ? <LogoLoader label={t`Loading choices…`} size={48} className="min-h-16 py-3" /> : list.isError ? <p role="alert">{t`Choices are unavailable for your access.`}</p> : <>
    {!list.data.results.length ? <p>{t`No choices are available.`}</p> : null}
    <ul className="grid gap-2">{list.data.results.filter(row => Number.isSafeInteger(row.id) && row.id > 0).map(row => <li key={row.id}>
      <button type="button" className="desk-button" onClick={() => onSelect(row.id)}>{row.title || t`Event #${row.id}`}{row.starts_at ? ` · ${formatDateTime(row.starts_at)}` : ""}</button>
    </li>)}</ul><Pager previous={list.data.previous} next={list.data.next} count={list.data.count} page={page} setPage={setPage} />
  </>}</div>;
}

function Pager({ previous, next, count, page, setPage }: { previous: string | null; next: string | null; count?: number; page: number; setPage: (page: number) => void }) {
  return <EventPanelPager page={page} setPage={setPage} count={count} previous={previous} next={next} />;
}

function BookingChoices({ tenant, scope, onSelect }: { tenant: number; scope: string; onSelect: (id: number) => void }) {
  const [space, setSpace] = useState<number | undefined>();
  const [spacePage, setSpacePage] = useState(1);
  const [bookingPage, setBookingPage] = useState(1);
  const spaces = useQuery({ queryKey: ["loan-context-choices", scope, "booking-spaces", spacePage],
    queryFn: () => staffRequest<Page>(`/admin/makerspaces/${tenant}/spaces/?page=${spacePage}`), retry: false });
  const bookings = useQuery({ queryKey: ["loan-context-choices", scope, "booking-rows", space, bookingPage],
    queryFn: () => staffRequest<Page>(`/admin/spaces/${space}/bookings/?page=${bookingPage}&ordering=starts_at`),
    enabled: Boolean(space), retry: false });
  return <div className="grid gap-2">
    <p>{t`Choose a space, then the specific booking.`}</p>
    {spaces.isPending ? <LogoLoader label={t`Loading spaces…`} size={48} className="min-h-16 py-3" /> : spaces.isError ? <p role="alert">{t`Spaces are unavailable for your access.`}</p> : <>
      {!spaces.data.results.length ? <p>{t`No spaces are available.`}</p> : null}
      <ul className="grid gap-2">{spaces.data.results.filter(row => Number.isSafeInteger(row.id) && row.id > 0).map(row => <li key={row.id}>
        <button type="button" className="desk-button" aria-pressed={space === row.id} onClick={() => { setSpace(row.id); setBookingPage(1); }}>{row.name || t`Space #${row.id}`}</button>
      </li>)}</ul><Pager previous={spaces.data.previous} next={spaces.data.next} count={spaces.data.count} page={spacePage} setPage={setSpacePage} />
    </>}
    {space ? bookings.isPending ? <LogoLoader label={t`Loading bookings…`} size={48} className="min-h-16 py-3" /> : bookings.isError ? <p role="alert">{t`Bookings are unavailable for your access.`}</p> : <>
      {!bookings.data.results.length ? <p>{t`No bookings are available.`}</p> : null}
      <ul className="grid gap-2">{bookings.data.results.filter(row => Number.isSafeInteger(row.id) && row.id > 0).map(row => <li key={row.id}>
        <button type="button" className="desk-button" onClick={() => onSelect(row.id)}>{t`Booking #${row.id}`}{row.starts_at ? ` · ${formatDateTime(row.starts_at)}` : ""}</button>
      </li>)}</ul><Pager previous={bookings.data.previous} next={bookings.data.next} count={bookings.data.count} page={bookingPage} setPage={setBookingPage} />
    </> : null}
  </div>;
}

export function Choices({ tenant, domain, scope, onSelect }: { tenant: number; domain: Domain; scope: string; onSelect: (id: number) => void }) {
  return domain === "event" ? <EventChoices tenant={tenant} scope={scope} onSelect={onSelect} /> : <BookingChoices tenant={tenant} scope={scope} onSelect={onSelect} />;
}

type Registration = { id: number; name?: string; status?: string };
export function Participants({ eventId, scope, value, onChange }: { eventId: number; scope: string; value: number | null | undefined; onChange: (id: number | null) => void }) {
  const [page, setPage] = useState(1);
  const list = useQuery({ queryKey: ["loan-context-participants", scope, eventId, page],
    queryFn: () => staffRequest<{ count?: number; results: Registration[]; next: string | null; previous: string | null }>(`/admin/events/${eventId}/registrations/?page=${page}`), retry: false });
  return <fieldset className="grid gap-2"><legend>{t`Event participant`}</legend>
    <p className="text-sm text-muted">{t`The participant is context and does not change the borrower.`}</p>
    <button type="button" className="desk-button" aria-pressed={value === null} onClick={() => onChange(null)}>{t`No participant`}</button>
    {list.isPending ? <LogoLoader label={t`Loading participants…`} size={48} className="min-h-16 py-3" /> : list.isError ? <p role="alert">{t`Participants are unavailable for your access.`}</p> : <>
      <ul className="grid gap-2">{list.data.results.filter(row => Number.isSafeInteger(row.id) && row.id > 0).map(row => <li key={row.id}>
        <button type="button" className="desk-button" aria-pressed={value === row.id} onClick={() => onChange(row.id)}>{row.name || t`Participant #${row.id}`}{row.status ? ` · ${opsStatusLabel(row.status)}` : ""}</button>
      </li>)}</ul><EventPanelPager page={page} setPage={setPage} count={list.data.count} next={list.data.next} />
    </>}
  </fieldset>;
}

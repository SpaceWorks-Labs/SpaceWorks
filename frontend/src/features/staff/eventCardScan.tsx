// Scan a card at the event door (#132d1, Q-I10). A member card, this event's ID card or a
// programme card's check link identifies the person; door staff then confirm, exactly like a
// ticket. A scan never signs anyone in. One confirmable registration is checked in through
// the card route (recorded as a card scan); several are listed for staff to pick from.
import { t } from "@lingui/core/macro";
import { staffRequest } from "../../lib/api";
import { opsStatusLabel } from "./opsPresentation";

export type CardScanRow = { registration_id: number; name: string; status: string; confirmable: boolean };
export type CardScanResult = { checked_in: number | null; registrations: CardScanRow[] };
export type CardMatch = { payload: string; rows: CardScanRow[] };

/** Plain request (no query cache): finding is read-only; `checkIn` records attendance for one confirmable match. */
export function scanEventCard(eventId: number, payload: string, checkIn = false) {
  return staffRequest<CardScanResult>(`/admin/events/${eventId}/check-in/card-scan`, {
    method: "POST", body: JSON.stringify({ payload, check_in: checkIn }) });
}

export function cardMatchSummary(match: CardMatch) {
  const confirmable = match.rows.filter((row) => row.confirmable);
  if (match.rows.length === 1) {
    const [row] = match.rows;
    return { title: row.name, confirmable: row.confirmable,
      note: row.confirmable ? t`Found by their card.` : t`Found by their card, but this registration is ${opsStatusLabel(row.status).toLowerCase()}.` };
  }
  return { title: t`${match.rows.length} registrations for this card`, confirmable: false,
    note: confirmable.length ? t`Pick the one to check in.` : t`None of them can be checked in now.` };
}

export function CardMatchList({ match, pending, onPick }: { match: CardMatch; pending: boolean; onPick: (row: CardScanRow) => void }) {
  if (match.rows.length < 2) return null;
  return <ul className="grid gap-2" aria-label={t`Registrations found by this card`}>
    {match.rows.map((row) => <li key={row.registration_id} className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-line p-2">
      <span className="text-sm text-ink">{row.name} <span className="text-xs text-muted">· {opsStatusLabel(row.status)}</span></span>
      <button type="button" className="desk-button min-h-11" disabled={!row.confirmable || pending} onClick={() => onPick(row)}>
        {t`Check in ${row.name}`}</button>
    </li>)}
  </ul>;
}

import { t } from "@lingui/core/macro";

type EventChoice = { registrationId: number; label: string };
type BookingChoice = { token: string; label: string };
export type EquipmentPurposeValue = { eventRegistrationId: number | null; bookingToken: string | null };

/** Choices must come from owner-scoped APIs; server reauthorizes at submission. */
export function EquipmentPurpose({ value, onChange, events, bookings, eventsEnabled, bookingsEnabled, disabled = false }: {
  value: EquipmentPurposeValue; onChange: (value: EquipmentPurposeValue) => void;
  events: readonly EventChoice[]; bookings: readonly BookingChoice[]; eventsEnabled: boolean; bookingsEnabled: boolean; disabled?: boolean;
}) {
  return <fieldset className="grid gap-3" disabled={disabled} data-replay-block>
    <legend className="text-sm font-semibold text-ink">{t`Equipment purpose`}</legend>
    <p className="text-sm text-muted">{t`Optionally link your event or booking. Staff review the request before anything is issued.`}</p>
    {eventsEnabled ? <label className="grid gap-1 text-sm">{t`Your event`}
      <select className="desk-input" value={value.eventRegistrationId ?? ""} onChange={e => onChange({ ...value, eventRegistrationId: e.target.value ? Number(e.target.value) : null })}>
        <option value="">{t`No event`}</option>{events.map(row => <option key={row.registrationId} value={row.registrationId}>{row.label}</option>)}
      </select></label> : null}
    {bookingsEnabled ? <label className="grid gap-1 text-sm">{t`Your booking`}
      <select className="desk-input" value={value.bookingToken ?? ""} onChange={e => onChange({ ...value, bookingToken: e.target.value || null })}>
        <option value="">{t`No booking`}</option>{bookings.map(row => <option key={row.token} value={row.token}>{row.label}</option>)}
      </select></label> : null}
  </fieldset>;
}

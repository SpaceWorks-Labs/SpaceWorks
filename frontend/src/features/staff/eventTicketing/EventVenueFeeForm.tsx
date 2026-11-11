import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Card } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import { AsyncSearchPicker, type PickerOption } from "../AsyncSearchPicker";
import { panelField, panelInput } from "../eventPanelStyles";
import { useSpeakerCandidates } from "../eventSpeakersApi";
import { useEvent } from "../eventsApi";
import { eventErrorText } from "../eventUi";
import { useEventRoomChoices } from "../eventVenueApi";
import { useVenueFee, type VenueFeeInput } from "./staffTicketingApi";

const blank: VenueFeeInput = { payer_id: 0, mode: "inherit", basis: "flat", amount: null, room_id: null };

const relationLabel = (relation: string) => relation === "member" ? t`Member` : relation === "staff" ? t`Event staff` : t`Registered for this event`;

/** #128 C-20: what an outside organiser pays to host this event. Charged once, when the event is published.
 * Open items B9: the payer and the room are picked by name, never typed as raw ids. */
export function EventVenueFeeForm({ eventId, disabled = false }: { eventId: number; disabled?: boolean }) {
  const { fee, save, charge } = useVenueFee(eventId);
  const event = useEvent(eventId);
  const makerspaceId = event.data?.makerspace_id ?? 0;
  const rooms = useEventRoomChoices(makerspaceId, Boolean(makerspaceId));
  const [values, setValues] = useState(blank);
  const [payer, setPayer] = useState<PickerOption | null>(null);
  const [term, setTerm] = useState("");
  const candidates = useSpeakerCandidates(eventId, term);
  useEffect(() => {
    if (!fee.data) return;
    setValues({ payer_id: fee.data.payer, mode: fee.data.mode, basis: fee.data.basis, amount: fee.data.amount,
      room_id: fee.data.room, organization_id: fee.data.organization });
    setPayer({ id: fee.data.payer, label: fee.data.payer_name });
  }, [fee.data]);
  const set = <K extends keyof VenueFeeInput>(key: K, value: VenueFeeInput[K]) => setValues(current => ({ ...current, [key]: value }));
  const charged = Boolean(fee.data && fee.data.status !== "configured");
  const locked = disabled || charged;
  const error = save.error || charge.error;
  const options: PickerOption[] = (candidates.data?.results ?? []).map(row => ({ id: row.id, label: row.display_name || row.username,
    detail: relationLabel(row.relation) }));
  const roomRows = rooms.data?.results ?? [];
  // A room set before (or no longer offered) stays selectable so saving never drops it silently.
  const knownRoom = values.room_id && !roomRows.some(room => room.id === values.room_id) ? values.room_id : null;
  return <Card><form className="grid gap-4" aria-label={t`Venue fee`} onSubmit={submit => { submit.preventDefault();
    if (!values.payer_id) return;
    save.mutate({ ...values, amount: values.mode === "custom" ? values.amount ?? "0.00" : null }); }}>
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="title-section">{t`Venue fee for hosting`}</h3>
      <ScreenHelp screen="events.venue-fees" className="" /></div>
    {fee.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading the venue fee…`}</p> : null}
    {fee.data ? <p className="text-sm text-muted">{fee.data.status === "charged" ? t`${fee.data.payer_name} pays ${fee.data.quote_total} · charged.`
      : fee.data.status === "free" ? t`${fee.data.payer_name} pays ${fee.data.quote_total} · nothing to charge.`
      : t`${fee.data.payer_name} pays ${fee.data.quote_total} · charged when the event is published.`}</p> : null}
    <AsyncSearchPicker label={t`Who pays`} helper={t`Search this space's members, event staff and people registered for this event. Type at least two characters.`}
      placeholder={t`Search by name or username`} selected={payer ? [payer] : []} options={options}
      loading={term.length >= 2 && candidates.isFetching} error={candidates.error ? eventErrorText(candidates.error) : null}
      emptyText={term.length >= 2 ? t`No matching accounts.` : t`Type at least two characters.`} disabled={locked}
      onSearch={setTerm} onChange={next => { const picked = next[next.length - 1] ?? null; setPayer(picked); set("payer_id", picked?.id ?? 0); }} />
    <label className={panelField}>{t`Room (optional, its venue price applies)`}<select className={panelInput} value={values.room_id ?? ""} disabled={locked || rooms.isLoading}
        onChange={change => set("room_id", change.target.value ? Number(change.target.value) : null)}>
      <option value="">{t`No room`}</option>
      {roomRows.map(room => <option key={room.id} value={room.id}>{room.capacity ? t`${room.name} (fits ${room.capacity})` : room.name}</option>)}
      {knownRoom ? <option value={knownRoom}>{t`The room set before`}</option> : null}
    </select></label>
    {rooms.isError ? <p className="text-sm text-muted">{t`Rooms can't be listed here (Bookings may be off). The fee can still use the space price.`}</p> : null}
    <p className="text-sm text-muted">{t`If a room booking already covers this event, link that booking to the event instead. A fee for the same room and time is refused so the room is not charged twice.`}</p>
    <label className={panelField}>{t`Price`}<select className={panelInput} value={values.mode} disabled={locked}
      onChange={change => set("mode", change.target.value as VenueFeeInput["mode"])}>
      <option value="inherit">{t`Room or space price`}</option><option value="free">{t`Free`}</option><option value="custom">{t`Custom`}</option></select></label>
    {values.mode === "custom" ? <>
      <label className={panelField}>{t`Amount`}<input className={panelInput} type="number" min="0" step="0.01" value={values.amount ?? ""}
        disabled={locked} onChange={change => set("amount", change.target.value)} /></label>
      <label className={panelField}>{t`Charged`}<select className={panelInput} value={values.basis} disabled={locked}
        onChange={change => set("basis", change.target.value as VenueFeeInput["basis"])}>
        <option value="flat">{t`Once`}</option><option value="per_hour">{t`Per hour of the event`}</option></select></label>
    </> : null}
    {error ? <p role="alert" className="text-sm text-danger">{eventErrorText(error)}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button className="desk-button-primary" type="submit" disabled={locked || save.isPending || !values.payer_id}>{t`Save venue fee`}</button>
      {fee.data?.status === "configured" ? <button className="desk-button" type="button" disabled={disabled || charge.isPending}
        onClick={() => charge.mutate()}>{t`Charge now`}</button> : null}
    </div>
  </form></Card>;
}

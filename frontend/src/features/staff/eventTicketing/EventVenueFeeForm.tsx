import { useEffect, useState } from "react";
import { Card } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import { panelField, panelInput } from "../eventPanelStyles";
import { useVenueFee, type VenueFeeInput } from "./staffTicketingApi";

const blank: VenueFeeInput = { payer_id: 0, mode: "inherit", basis: "flat", amount: null, room_id: null };

/** #128 C-20: what an outside organiser pays to host this event. Charged once, when the event is published. */
export function EventVenueFeeForm({ eventId, disabled = false }: { eventId: number; disabled?: boolean }) {
  const { fee, save, charge } = useVenueFee(eventId);
  const [values, setValues] = useState(blank);
  useEffect(() => {
    if (fee.data) setValues({ payer_id: fee.data.payer, mode: fee.data.mode, basis: fee.data.basis, amount: fee.data.amount,
      room_id: fee.data.room, organization_id: fee.data.organization });
  }, [fee.data]);
  const set = <K extends keyof VenueFeeInput>(key: K, value: VenueFeeInput[K]) => setValues(current => ({ ...current, [key]: value }));
  const charged = fee.data && fee.data.status !== "configured";
  const error = save.error || charge.error;
  return <Card><form className="grid gap-4" aria-label="Venue fee" onSubmit={event => { event.preventDefault();
    save.mutate({ ...values, amount: values.mode === "custom" ? values.amount ?? "0.00" : null }); }}>
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="title-section">Venue fee for hosting</h3>
      <ScreenHelp screen="events.venue-fees" className="" /></div>
    {fee.data ? <p className="text-sm text-muted">{fee.data.payer_name} pays {fee.data.quote_total}
      {fee.data.status === "charged" ? " · charged" : fee.data.status === "free" ? " · nothing to charge" : " · charged when the event is published"}.</p> : null}
    <label className={panelField}>Payer account number
      <input className={panelInput} type="number" min="1" required value={values.payer_id || ""} disabled={disabled || Boolean(charged)}
        onChange={event => set("payer_id", Number(event.target.value))} /></label>
    <label className={panelField}>Room (optional, its venue price applies)
      <input className={panelInput} type="number" min="1" value={values.room_id ?? ""} disabled={disabled || Boolean(charged)}
        onChange={event => set("room_id", event.target.value ? Number(event.target.value) : null)} /></label>
    <label className={panelField}>Price<select className={panelInput} value={values.mode} disabled={disabled || Boolean(charged)}
      onChange={event => set("mode", event.target.value as VenueFeeInput["mode"])}>
      <option value="inherit">Room or space price</option><option value="free">Free</option><option value="custom">Custom</option></select></label>
    {values.mode === "custom" ? <>
      <label className={panelField}>Amount<input className={panelInput} type="number" min="0" step="0.01" value={values.amount ?? ""}
        disabled={disabled || Boolean(charged)} onChange={event => set("amount", event.target.value)} /></label>
      <label className={panelField}>Charged<select className={panelInput} value={values.basis} disabled={disabled || Boolean(charged)}
        onChange={event => set("basis", event.target.value as VenueFeeInput["basis"])}>
        <option value="flat">Once</option><option value="per_hour">Per hour of the event</option></select></label>
    </> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button className="desk-button-primary" type="submit" disabled={disabled || Boolean(charged) || save.isPending}>Save venue fee</button>
      {fee.data?.status === "configured" ? <button className="desk-button" type="button" disabled={disabled || charge.isPending}
        onClick={() => charge.mutate()}>Charge now</button> : null}
    </div>
  </form></Card>;
}

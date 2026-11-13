import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Repeat } from "lucide-react";
import { Card } from "../../../components/ui";
import { panelField, panelInput } from "../eventPanelStyles";
import { useSalesSettings, type SalesSettings } from "./staffTicketingApi";

const DEFAULTS: SalesSettings = { booking_fee_fixed: "0.00", booking_fee_bps: 0, max_tickets_per_order: 10,
  transfers_allowed: false, type_changes_allowed: false, transfer_cutoff_hours: 0 };

/** Booking fee, order size and the transfer / type-change switches for one event. */
export function EventSalesRules({ eventId, transfers, disabled = false }: { eventId: number; transfers: boolean; disabled?: boolean }) {
  const { settings, save } = useSalesSettings(eventId);
  const [values, setValues] = useState<SalesSettings>(DEFAULTS);
  useEffect(() => { if (settings.data) setValues(settings.data); }, [settings.data]);
  const set = <K extends keyof SalesSettings>(key: K, value: SalesSettings[K]) => setValues(current => ({ ...current, [key]: value }));
  return <Card><form className="grid gap-4" aria-label={t`Sales rules`} onSubmit={event => { event.preventDefault(); save.mutate(values); }}>
    <h3 className="title-section">{t`Sales rules`}</h3>
    <label className={panelField}>{t`Booking fee, fixed per order`}<input className={panelInput} type="number" min="0" step="any" value={values.booking_fee_fixed} disabled={disabled}
        onChange={event => set("booking_fee_fixed", event.target.value)} /></label>
    <label className={panelField}>{t`Booking fee, percent of tickets`}<input className={panelInput} type="number" min="0" max="100" step="0.01" value={values.booking_fee_bps / 100} disabled={disabled}
        onChange={event => set("booking_fee_bps", Math.round(Number(event.target.value) * 100))} /></label>
    <label className={panelField}>{t`Most tickets in one order`}<input className={panelInput} type="number" min="1" value={values.max_tickets_per_order} disabled={disabled}
        onChange={event => set("max_tickets_per_order", Number(event.target.value))} /></label>
    {transfers ? <fieldset className="grid gap-2">
      <legend className="flex items-center gap-2 text-sm font-semibold"><Repeat aria-hidden="true" size={16} />{t`Transfers`}</legend>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={values.transfers_allowed} disabled={disabled}
        onChange={event => set("transfers_allowed", event.target.checked)} />{t`Attendees may pass their ticket to someone else`}</label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={values.type_changes_allowed} disabled={disabled}
        onChange={event => set("type_changes_allowed", event.target.checked)} />{t`Attendees may change ticket type`}</label>
      <label className={panelField}>{t`Stop transfers this many hours before the start`}<input className={panelInput} type="number" min="0" value={values.transfer_cutoff_hours} disabled={disabled}
          onChange={event => set("transfer_cutoff_hours", Number(event.target.value))} /></label>
    </fieldset> : null}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || save.isPending}>{t`Save sales rules`}</button>
  </form></Card>;
}

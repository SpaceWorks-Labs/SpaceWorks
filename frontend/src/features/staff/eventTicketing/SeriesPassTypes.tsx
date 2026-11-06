import { t } from "@lingui/core/macro";
import { useContext, useState } from "react";
import { QueryClientContext } from "@tanstack/react-query";
import { Repeat } from "lucide-react";
import { Card } from "../../../components/ui";
import { ScreenHelp } from "../../help/HelpLink";
import { capabilityOn } from "../../../lib/features";
import { panelEmpty, panelField, panelInput, panelRow } from "../eventPanelStyles";
import { usePassTypes, type PassType } from "./staffTicketingApi";
import { useStaffChargesOn } from "../useStaffChargesOn";

type SpaceFlags = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** Is a capability on in this makerspace? Read from the staff session's cached list, never fetched here
 * (and safely off where no query client is mounted). */
export function useStaffCapability(makerspaceId: number, key: string) {
  const client = useContext(QueryClientContext);
  const spaces = client?.getQueryData<SpaceFlags[]>(["staff", "makerspaces"]);
  const space = Array.isArray(spaces) ? spaces.find(row => row.id === makerspaceId) : undefined;
  return space ? capabilityOn(space, key) : false;
}

const blank: PassType = { name: "", amount: "0.00", capacity: 0, occurrence_refund_amount: "0.00", sales_end_at: null, is_active: true };

/** G31: one pass for every future occurrence. The per-occurrence amount is owed (staff approve) if one is cancelled. */
export function SeriesPassTypes({ seriesId, disabled = false }: { seriesId: number; disabled?: boolean }) {
  const { rows, save } = usePassTypes(seriesId);
  const [draft, setDraft] = useState<PassType>(blank);
  const set = <K extends keyof PassType>(key: K, value: PassType[K]) => setDraft(current => ({ ...current, [key]: value }));
  // #184: a series pass is only ever sold, so a free events domain has nothing to set up here.
  const chargesOn = useStaffChargesOn("events");
  if (!chargesOn) return <p className="text-sm text-muted">{t`Event charges are off in this space, so events are free.`}</p>;
  return <section className="grid gap-3" aria-label={t`Series passes`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="title-section flex items-center gap-2"><Repeat aria-hidden="true" size={18} />{t`Series passes`}</h3>
      <ScreenHelp screen="events.series-passes" className="" /></div>
    <Card><form className="grid gap-4" onSubmit={event => { event.preventDefault(); save.mutate(draft, { onSuccess: () => setDraft(blank) }); }}>
      <label className={panelField}>{t`Name`}<input className={panelInput} required maxLength={100} value={draft.name} disabled={disabled} onChange={event => set("name", event.target.value)} /></label>
      <label className={panelField}>{t`Price`}<input className={panelInput} type="number" min="0" step="0.01" value={draft.amount} disabled={disabled} onChange={event => set("amount", event.target.value)} /></label>
      <label className={panelField}>{t`Passes available (0 = unlimited)`}<input className={panelInput} type="number" min="0" value={draft.capacity} disabled={disabled} onChange={event => set("capacity", Number(event.target.value))} /></label>
      <label className={panelField}>{t`Owed back per cancelled occurrence`}<input className={panelInput} type="number" min="0" step="0.01" value={draft.occurrence_refund_amount} disabled={disabled} onChange={event => set("occurrence_refund_amount", event.target.value)} /></label>
      {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
      <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || save.isPending}>{t`Add pass`}</button>
    </form></Card>
    {rows.data?.results.length === 0 ? <p className={panelEmpty}>{t`No passes yet.`}</p> : null}
    <ul className="grid gap-3">{rows.data?.results.map(pass => <li key={pass.id} className={panelRow}>
      <span className="grid gap-0.5"><span className="font-semibold text-ink">{pass.name}{pass.is_active ? "" : " (off)"}</span>
        <span className="text-sm text-muted">{t`${pass.amount} · sold ${pass.sold ?? 0} · ${pass.occurrence_refund_amount} back per cancelled date`}</span></span>
      <button className="desk-button" type="button" disabled={disabled} onClick={() => save.mutate({ ...pass, is_active: !pass.is_active })}>
        {pass.is_active ? t`Stop selling` : t`Sell again`}</button>
    </li>)}</ul>
  </section>;
}

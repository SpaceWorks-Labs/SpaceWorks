import { t } from "@lingui/core/macro";
import { useState } from "react";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { AttributeChips } from "./AttributeChips";
import { useConsumableStock } from "./consumablesApi";
import { blankDraft, draftProblem, keyFromName, withUnit, type ProfileDraft } from "./profileDraft";
import { ESTIMATE_BY, KINDS, RECORD_BY, UNITS, type ConsumableUnit, type EstimateBy, type RecordBy } from "./profileUnits";
import { StockLinkPicker } from "./StockLinkPicker";

/** One profile row's form: used for a new custom row and for editing an existing one (the key and a used row's unit are fixed). */
export function ConsumableRowEditor({ makerspaceId = 0, typeId = 0, initial, isNew, unitLocked = false, currency, templateMode = false, saving, error, onSave, onCancel }: {
  makerspaceId?: number; typeId?: number; initial?: ProfileDraft; isNew: boolean; unitLocked?: boolean; currency?: string;
  /** A template row: no price, stock link or ids, just the shape a new type starts with. */
  templateMode?: boolean;
  saving: boolean; error?: string; onSave: (draft: ProfileDraft) => void; onCancel: () => void;
}) {
  const [draft, setDraft] = useState<ProfileDraft>(initial ?? blankDraft);
  const [keyTouched, setKeyTouched] = useState(Boolean(initial));
  const stock = useConsumableStock(makerspaceId, typeId, "", !templateMode);
  const set = (patch: Partial<ProfileDraft>) => setDraft(current => ({ ...current, ...patch }));
  const problem = draftProblem(draft, isNew);
  const toggleRecord = (value: RecordBy, on: boolean) => set({ record_by: on ? [...draft.record_by, value] : draft.record_by.filter(item => item !== value) });
  const priceLabel = currency ? t`Price per unit (${currency})` : t`Price per unit`;
  return <form className="grid gap-3 rounded-xl border border-line bg-bg p-3" onSubmit={event => { event.preventDefault(); if (!problem) onSave(draft); }}>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Name`}<input className="desk-input" value={draft.name} maxLength={100} required
        onChange={event => set({ name: event.target.value, ...(isNew && !keyTouched ? { key: keyFromName(event.target.value) } : {}) })} /></label>
      <label className="grid gap-1 text-sm">{t`Key`}<input className="desk-input code-text" value={draft.key} disabled={!isNew} maxLength={50}
        onChange={event => { setKeyTouched(true); set({ key: event.target.value }); }} /></label>
      <label className="grid gap-1 text-sm">{t`Kind`}<select className="desk-input" value={draft.kind} onChange={event => set({ kind: event.target.value as ProfileDraft["kind"] })}>
        {KINDS().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="grid gap-1 text-sm">{t`Unit`}<select className="desk-input" value={draft.unit} disabled={unitLocked}
        onChange={event => setDraft(current => withUnit(current, event.target.value as ConsumableUnit, id => stock.data?.pools.find(pool => pool.id === id)?.unit))}>
        {UNITS().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        {unitLocked ? <span className="text-xs text-muted">{t`The unit can't change once jobs have used this consumable.`}</span> : null}</label>
      <label className="grid gap-1 text-sm">{t`Who estimates it`}<select className="desk-input" value={draft.estimate_by} onChange={event => set({ estimate_by: event.target.value as EstimateBy })}>
        {ESTIMATE_BY().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {templateMode ? null : <label className="grid gap-1 text-sm">{priceLabel}<input className="desk-input tabular-nums" inputMode="decimal" value={draft.unit_price} placeholder={t`Not charged on its own`}
        onChange={event => set({ unit_price: event.target.value })} /></label>}
    </div>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={draft.required} onChange={event => set({ required: event.target.checked })} />
      {t`Required: a job can't be completed until this is recorded`}</label>
    <fieldset className="grid gap-1"><legend className="eyebrow">{t`Recorded by`}</legend>
      <div className="flex flex-wrap gap-x-4">{RECORD_BY().map(([value, label]) => <label key={value} className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={draft.record_by.includes(value)} onChange={event => toggleRecord(value, event.target.checked)} />{label}</label>)}</div></fieldset>
    <AttributeChips value={draft.attributes} onChange={attributes => set({ attributes })} />
    {templateMode ? null : <StockLinkPicker makerspaceId={makerspaceId} typeId={typeId} draft={draft} onChange={set} />}
    {problem ? <p className="text-sm text-muted" role="status">{problem}</p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <div className="flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button-ghost min-h-11" onClick={onCancel}>{t`Cancel`}</button>
      <button type="submit" className="desk-button-primary min-h-11" disabled={!!problem || saving}>{saving ? <><BoxArt size={16} mono />{t`Saving…`}</> : isNew ? t`Add consumable` : t`Save consumable`}</button>
    </div>
  </form>;
}

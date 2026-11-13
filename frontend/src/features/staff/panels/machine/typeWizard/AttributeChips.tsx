import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ATTRIBUTES, type AttributeKey, type ProfileAttributes } from "./profileUnits";

function ChipList({ label, values, onChange }: { label: string; values: string[]; onChange: (values: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const value = draft.trim();
    if (value && !values.includes(value)) onChange([...values, value]);
    setDraft("");
  };
  return <div className="grid gap-2">
    <ul className="flex flex-wrap gap-1" aria-label={t`${label} choices`}>
      {values.map(value => <li key={value} className="flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-1 text-sm">
        <span className="min-w-0 break-words">{value}</span>
        <button type="button" className="min-h-8 min-w-8 rounded-full text-muted" aria-label={t`Remove ${value}`} onClick={() => onChange(values.filter(item => item !== value))}>×</button>
      </li>)}
    </ul>
    <div className="flex gap-2">
      <input className="desk-input min-w-0 flex-1" aria-label={t`Add a ${label} choice`} value={draft} maxLength={60} placeholder={t`Add a choice`}
        onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); add(); } }} />
      <button type="button" className="desk-button-ghost" onClick={add} disabled={!draft.trim()}>{t`Add`}</button>
    </div>
    {values.length === 0 ? <p className="text-xs text-muted">{t`No choices: the member types it in.`}</p> : null}
  </div>;
}

/** The attributes a member or staff member describes a consumable with. A listed attribute with no choices is free text. */
export function AttributeChips({ value, onChange }: { value: ProfileAttributes; onChange: (value: ProfileAttributes) => void }) {
  const toggle = (key: AttributeKey, on: boolean) => {
    const next = { ...value };
    if (on) next[key] = []; else delete next[key];
    onChange(next);
  };
  return <fieldset className="grid gap-3">
    <legend className="eyebrow">{t`Details to ask about`}</legend>
    {ATTRIBUTES().map(([key, label]) => <div key={key} className="grid gap-2 rounded-lg border border-line p-2">
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={value[key] !== undefined} onChange={event => toggle(key, event.target.checked)} />{label}</label>
      {value[key] !== undefined ? <ChipList label={label} values={value[key] ?? []} onChange={values => onChange({ ...value, [key]: values })} /> : null}
    </div>)}
  </fieldset>;
}

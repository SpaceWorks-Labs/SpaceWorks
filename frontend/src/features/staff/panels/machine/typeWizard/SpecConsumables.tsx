import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Badge } from "../../../../../components/ui";
import { ConsumableRowEditor } from "./ConsumableRowEditor";
import type { ConsumableDefinition } from "./consumablesApi";
import { blankDraft, type ProfileDraft } from "./profileDraft";
import { KINDS, unitShort } from "./profileUnits";

type Row = Partial<ConsumableDefinition>;
const fromRow = (row: Row): ProfileDraft => ({ ...blankDraft(), key: row.key ?? "", name: row.name ?? "", kind: row.kind ?? "material", unit: row.unit ?? "g",
  attributes: row.attributes ?? {}, required: row.required ?? false, estimate_by: row.estimate_by ?? "none", record_by: row.record_by ?? ["staff"] });
/** A template row holds the shape only: no ids, prices, stock links or position. */
const toRow = (draft: ProfileDraft): Row => ({ key: draft.key, name: draft.name.trim(), kind: draft.kind, unit: draft.unit, required: draft.required,
  estimate_by: draft.estimate_by, record_by: draft.record_by, attributes: draft.attributes });

/** The template's consumable rows, edited with the profile row editor in template mode. */
export function SpecConsumables({ rows, onChange }: { rows: Row[]; onChange: (next: Row[]) => void }) {
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const move = (index: number, by: -1 | 1) => { const next = [...rows]; [next[index], next[index + by]] = [next[index + by], next[index]]; onChange(next); };
  const done = () => setEditing(null);
  return <div className="grid gap-2">
    {!rows.length ? <p className="text-sm text-muted">{t`No consumables yet.`}</p> : null}
    <ul className="grid gap-2">{rows.map((row, index) => <li key={`${row.key}-${index}`} className="grid gap-2 rounded-lg border border-line p-3">
      {editing === index ? <ConsumableRowEditor templateMode isNew initial={fromRow(row)} saving={false} onCancel={done}
        onSave={draft => { onChange(rows.map((item, at) => at === index ? toRow(draft) : item)); done(); }} /> : <>
        <div className="flex flex-wrap items-center justify-between gap-2"><strong className="min-w-0 break-words">{row.name || row.key}</strong>
          {row.required ? <Badge tone="warn">{t`Required`}</Badge> : null}</div>
        <p className="text-sm text-muted">{[KINDS().find(([kind]) => kind === row.kind)?.[1], row.unit ? unitShort(row.unit) : "", row.key].filter(Boolean).join(" · ")}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Edit consumable ${row.name ?? row.key ?? ""}`} onClick={() => setEditing(index)}>{t`Edit`}</button>
          <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Move ${row.name ?? row.key ?? ""} up`} disabled={index === 0} onClick={() => move(index, -1)}>{t`Up`}</button>
          <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Move ${row.name ?? row.key ?? ""} down`} disabled={index === rows.length - 1} onClick={() => move(index, 1)}>{t`Down`}</button>
          <button type="button" className="desk-button-danger min-h-11" aria-label={t`Remove consumable ${row.name ?? row.key ?? ""}`} onClick={() => onChange(rows.filter((_, at) => at !== index))}>{t`Remove`}</button></div></>}
    </li>)}</ul>
    {editing === "new" ? <ConsumableRowEditor templateMode isNew saving={false} onCancel={done} onSave={draft => { onChange([...rows, toRow(draft)]); done(); }} />
      : editing === null ? <div><button type="button" className="desk-button min-h-11" onClick={() => setEditing("new")}>{t`Add a consumable`}</button></div> : null}
  </div>;
}

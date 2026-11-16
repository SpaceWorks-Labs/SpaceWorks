import { t } from "@lingui/core/macro";
import { useState } from "react";

import { LogoLoader } from "../../../../../components/LogoLoader";
import { Badge, ConfirmDialog, EmptyState } from "../../../../../components/ui";
import { ConsumableRowEditor } from "./ConsumableRowEditor";
import { useConsumableProfile, useProfileMutations, type ConsumableDefinition } from "./consumablesApi";
import { draftBody, draftFromRow } from "./profileDraft";
import { KINDS, unitShort } from "./profileUnits";

const message = (error: unknown) => error instanceof Error ? error.message : undefined;

function RowSummary({ row }: { row: ConsumableDefinition }) {
  const attributes = Object.keys(row.attributes ?? {}).join(", ");
  return <p className="text-sm text-muted">{[KINDS().find(([kind]) => kind === row.kind)?.[1], unitShort(row.unit), attributes,
    row.consumable_pool_label || row.product_name, row.unit_price ? `${row.unit_price}/${unitShort(row.unit)}` : ""].filter(Boolean).join(" · ")}</p>;
}

/** The consumable profile of one machine type (decision 341): rows are added, edited, reordered and removed live against the API. */
export function ConsumableProfileEditor({ makerspaceId, typeId, currency, readOnly = false }: { makerspaceId: number; typeId: number; currency?: string; readOnly?: boolean }) {
  const profile = useConsumableProfile(makerspaceId, typeId);
  const { create, update, remove } = useProfileMutations(makerspaceId, typeId);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [removing, setRemoving] = useState<ConsumableDefinition | null>(null);
  const [notice, setNotice] = useState("");
  const rows = profile.data ?? [];
  const done = { onSuccess: () => setEditing(null) };
  const move = (index: number, by: -1 | 1) => {
    const a = rows[index]; const b = rows[index + by];
    if (!a || !b) return;
    update.mutate({ id: a.id, body: { position: index + by } });
    update.mutate({ id: b.id, body: { position: index } });
  };
  return <section className="grid gap-3" aria-label={t`Consumables`}>
    <p className="text-sm text-muted">{t`The materials and wear a job on this machine type uses. Required rows must be recorded before a job can be completed.`}</p>
    {profile.isLoading ? <LogoLoader label={t`Loading consumables…`} size={48} className="min-h-16 py-3" /> : null}
    {profile.isError ? <p role="alert" className="text-sm text-danger">{message(profile.error)}</p> : null}
    {profile.isSuccess && !rows.length ? <EmptyState message={t`No consumables yet. Add the first one below.`} /> : null}
    <ul className="grid gap-2">{rows.map((row, index) => <li key={row.id} className={`grid gap-2 rounded-lg border border-line p-3 ${row.is_active ? "" : "opacity-60"}`}>
      {editing === row.id ? <ConsumableRowEditor makerspaceId={makerspaceId} typeId={typeId} initial={draftFromRow(row)} isNew={false} unitLocked={row.in_use === true} currency={currency}
        saving={update.isPending} error={message(update.error)} onCancel={() => setEditing(null)}
        onSave={draft => update.mutate({ id: row.id, body: draftBody(draft, index) }, done)} /> : <>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <strong className="min-w-0 break-words">{row.name}</strong>
          <span className="flex flex-wrap gap-1">{row.required ? <Badge tone="warn">{t`Required`}</Badge> : null}{row.is_active ? null : <Badge tone="neutral">{t`Off`}</Badge>}</span></div>
        <RowSummary row={row} />
        {readOnly ? null : <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button-ghost min-h-11" onClick={() => { setNotice(""); setEditing(row.id); }}>{t`Edit`}</button>
          <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Move ${row.name} up`} disabled={index === 0 || update.isPending} onClick={() => move(index, -1)}>{t`Up`}</button>
          <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Move ${row.name} down`} disabled={index === rows.length - 1 || update.isPending} onClick={() => move(index, 1)}>{t`Down`}</button>
          <button type="button" className="desk-button-danger min-h-11" onClick={() => setRemoving(row)}>{t`Remove`}</button></div>}</>}
    </li>)}</ul>
    {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
    {!readOnly && editing === "new" ? <ConsumableRowEditor makerspaceId={makerspaceId} typeId={typeId} isNew currency={currency} saving={create.isPending} error={message(create.error)}
      onCancel={() => setEditing(null)} onSave={draft => create.mutate(draftBody(draft, rows.length), done)} /> : null}
    {!readOnly && editing === null ? <div><button type="button" className="desk-button min-h-11" onClick={() => { create.reset(); setEditing("new"); }}>{t`Add a custom consumable`}</button></div> : null}
    {remove.error ? <p role="alert" className="text-sm text-danger">{message(remove.error)}</p> : null}
    <ConfirmDialog open={removing !== null} title={t`Remove this consumable?`} tone="danger" confirmLabel={t`Remove`} pending={remove.isPending}
      message={t`A consumable already used by jobs is switched off instead of deleted, so history stays intact.`} onCancel={() => setRemoving(null)}
      onConfirm={() => { if (removing) remove.mutate(removing.id, { onSuccess: result => { setNotice(result.outcome === "deactivated" ? t`That consumable was already used, so it was switched off instead.` : t`Consumable removed.`); setRemoving(null); } }); }} />
  </section>;
}

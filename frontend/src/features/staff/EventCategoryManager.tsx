import { LogoLoader } from "../../components/LogoLoader";
import { plural, t } from "@lingui/core/macro";
import { useState } from "react";

import { ConfirmDialog } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { useEventCategories, useEventCategoryChanges, type EventCategory } from "./eventCategoriesApi";
import { eventErrorText } from "./eventUi";

function deleteError(error: unknown) {
  if (error instanceof StructuredApiError && error.status === 409 && error.code === "category_referenced") {
    return error.detail ?? t`Events use this category, so it can't be deleted. Move those events to another category first.`;
  }
  return eventErrorText(error);
}

function CategoryRow({ row, makerspaceId, disabled, onDeleted }: { row: EventCategory; makerspaceId: number; disabled: boolean; onDeleted: (id: number) => void }) {
  const { update, remove } = useEventCategoryChanges(makerspaceId);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(row.name);
  const [slug, setSlug] = useState(row.slug);
  const [confirming, setConfirming] = useState(false);
  const label = row.name || row.slug;
  return <li className="grid gap-2 rounded-xl border border-line bg-surface p-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="min-w-0 text-sm text-ink"><span className="font-semibold">{row.name}</span> <span className="code-text text-muted">{row.slug}</span>{row.event_count !== undefined ? <span className="text-muted"> · {plural(row.event_count, { one: "# event", other: "# events" })}</span> : null}</p>
      {!editing && !disabled ? <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" onClick={() => { update.reset(); setName(row.name); setSlug(row.slug); setEditing(true); }}>{t`Rename ${label}`}</button>
        <button className="desk-button-danger-outline" type="button" disabled={remove.isPending} onClick={() => { remove.reset(); setConfirming(true); }}>{t`Delete ${label}`}</button>
      </div> : null}
    </div>
    {editing ? <div className="grid gap-2 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Category name`}<input className="desk-input" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Category URL name`}<input className="desk-input" value={slug} maxLength={100} onChange={(e) => setSlug(e.target.value)} /></label>
      <div className="flex flex-wrap justify-end gap-2 sm:col-span-2">
        <button className="desk-button" type="button" disabled={update.isPending} onClick={() => setEditing(false)}>{t`Cancel`}</button>
        <button className="desk-button-primary" type="button" disabled={update.isPending || !name.trim() || !slug.trim()}
          onClick={() => update.mutate({ id: row.id, input: { ...(name !== row.name ? { name } : {}), ...(slug !== row.slug ? { slug } : {}) } }, { onSuccess: () => setEditing(false) })}>{t`Save category`}</button>
      </div>
    </div> : null}
    {update.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(update.error)}</p> : null}
    {remove.error ? <p role="alert" className="text-sm text-danger">{deleteError(remove.error)}</p> : null}
    <ConfirmDialog open={confirming} title={t`Delete category`} tone="danger" confirmLabel={t`Delete category`} pending={remove.isPending}
      message={t`Delete ${label}? Categories that events still use can't be deleted.`}
      onCancel={() => setConfirming(false)} onConfirm={() => remove.mutate(row.id, { onSuccess: () => onDeleted(row.id), onSettled: () => setConfirming(false) })} />
  </li>;
}

/** Rename, re-slug or delete this space's event categories. Mounted only while its disclosure is open. */
export function EventCategoryManager({ makerspaceId, disabled = false, onDeleted }: { makerspaceId: number; disabled?: boolean; onDeleted: (id: number) => void }) {
  const categories = useEventCategories(makerspaceId);
  if (categories.isLoading) return <LogoLoader label={t`Loading categories…`} />;
  if (!categories.data?.length) return <p className="text-sm text-muted">{t`No categories yet.`}</p>;
  return <ul className="grid gap-2" aria-label={t`Event categories`}>
    {categories.data.map((row) => <CategoryRow key={row.id} row={row} makerspaceId={makerspaceId} disabled={disabled} onDeleted={onDeleted} />)}
  </ul>;
}

import { useState } from "react";

import { EventCategoryManager } from "./EventCategoryManager";
import { useEventCategories, useEventCategoryChanges } from "./eventCategoriesApi";

const summary = "cursor-pointer py-3 text-sm font-semibold text-ink";

export function EventCategoriesField({ makerspaceId, value, onChange, disabled }: {
  makerspaceId: number; value: number | null; onChange: (id: number | null) => void; disabled?: boolean;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [managing, setManaging] = useState(false);
  const categories = useEventCategories(makerspaceId);
  const { create } = useEventCategoryChanges(makerspaceId);
  const add = () => create.mutate({ name, slug }, { onSuccess: (row) => { onChange(row.id); setName(""); setSlug(""); } });
  return <div className="grid gap-2 py-3">
    <label className="grid gap-1 text-sm">Event category<select className="desk-input" value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}><option value="">No category</option>{categories.data?.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
    <details><summary className={summary}>Add a category</summary><div className="grid gap-2"><label className="grid gap-1 text-sm">Category name<input className="desk-input" value={name} maxLength={100} disabled={disabled} onChange={(e) => setName(e.target.value)} /></label><label className="grid gap-1 text-sm">Category URL name<input className="desk-input" value={slug} maxLength={100} disabled={disabled} onChange={(e) => setSlug(e.target.value)} /></label><button className="desk-button" type="button" disabled={disabled || create.isPending || !name.trim() || !slug.trim()} onClick={add}>Add category</button></div></details>
    {/* The manager mounts on open, so the settings form never fetches per-row state nobody asked for. */}
    <details onToggle={(event) => setManaging(event.currentTarget.open)}><summary className={summary}>Manage categories</summary>
      {managing ? <EventCategoryManager makerspaceId={makerspaceId} disabled={disabled} onDeleted={(id) => { if (id === value) onChange(null); }} /> : null}
    </details>
    {categories.error || create.error ? <p role="alert">{(categories.error || create.error)?.message}</p> : null}
  </div>;
}

import { plural, t } from "@lingui/core/macro";
import { useState } from "react";

import { LogoLoader } from "../../../../../components/LogoLoader";
import { Badge, ConfirmDialog } from "../../../../../components/ui";
import { TemplateForm } from "./TemplateForm";
import { useDeleteTemplate, useSaveTemplate, useTemplates, type TypeTemplate } from "./templatesApi";

/** The space's machine-type template catalogue: built-ins plus the space's own copies. Space Manager only. */
export function TemplateCataloguePanel({ makerspaceId }: { makerspaceId: number }) {
  const templates = useTemplates(makerspaceId, true);
  const save = useSaveTemplate(makerspaceId);
  const remove = useDeleteTemplate(makerspaceId);
  const [editing, setEditing] = useState<{ key: string; copy: boolean } | null>(null);
  const [removing, setRemoving] = useState<TypeTemplate | null>(null);
  const finish = { onSuccess: () => setEditing(null) };
  return <details className="mb-4 overflow-hidden rounded-xl border border-line bg-panel">
    <summary className="min-h-11 cursor-pointer bg-surface px-4 py-3 text-sm font-semibold text-ink">{t`Machine type templates`}</summary>
    <div className="grid gap-3 p-3">
      <p className="text-sm text-muted">{t`Templates pre-fill the Add a machine type wizard. Save a customised copy of a built-in, or delete your copy to go back to the original.`}</p>
      {templates.isLoading ? <LogoLoader label={t`Loading templates…`} size={48} className="min-h-16 py-3" /> : null}
      {templates.isError ? <p role="alert" className="text-sm text-danger">{templates.error.message}</p> : null}
      <ul className="grid gap-2">{(templates.data ?? []).map(row => <li key={`${row.key}-${row.id}`} className="grid gap-2 rounded-lg border border-line p-3">
        {editing?.key === row.key ? <TemplateForm source={row} copy={editing.copy} saving={save.isPending} error={save.error?.message} onCancel={() => setEditing(null)} onSave={body => save.mutate(body, finish)} /> : <>
          <div className="flex flex-wrap items-center justify-between gap-2"><strong className="min-w-0 break-words">{row.name}</strong>
            <span className="flex flex-wrap gap-1">{row.is_builtin && !row.customised ? <Badge tone="neutral">{t`Built-in`}</Badge> : row.customised ? <Badge tone="info">{t`Customised`}</Badge> : <Badge tone="accent">{t`Your template`}</Badge>}
              {row.is_active ? null : <Badge tone="warn">{t`Hidden`}</Badge>}</span></div>
          <p className="text-sm text-muted">{[row.category, plural(row.spec.consumables.length, { one: "# consumable", other: "# consumables" }), row.description].filter(Boolean).join(" · ")}</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="desk-button min-h-11" onClick={() => { save.reset(); setEditing({ key: row.key, copy: false }); }}>{row.is_builtin && !row.customised ? t`Customise a copy` : t`Edit`}</button>
            <button type="button" className="desk-button-ghost min-h-11" onClick={() => { save.reset(); setEditing({ key: row.key, copy: true }); }}>{t`Duplicate as new`}</button>
            {!row.is_builtin || row.customised ? <button type="button" className="desk-button-danger min-h-11" onClick={() => setRemoving(row)}>{row.is_builtin ? t`Revert to built-in` : t`Delete`}</button> : null}</div></>}
      </li>)}</ul>
      {remove.error ? <p role="alert" className="text-sm text-danger">{remove.error.message}</p> : null}
      <ConfirmDialog open={removing !== null} tone="danger" title={removing?.is_builtin ? t`Revert to the built-in template?` : t`Delete this template?`} confirmLabel={removing?.is_builtin ? t`Revert` : t`Delete`}
        message={t`Machine types already created from it are not changed.`} pending={remove.isPending} onCancel={() => setRemoving(null)}
        onConfirm={() => { if (removing) remove.mutate(removing.key, { onSuccess: () => setRemoving(null) }); }} />
    </div>
  </details>;
}

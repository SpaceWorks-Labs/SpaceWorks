import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ErrorText, Field } from "../../../components/ui";
import { MAX_LEVELS } from "./unitHierarchy";
import { unitErrorText, unitKeys, unitsApi, type LevelTemplate } from "./unitsApi";

/** The three ready-made templates, named in the viewer's language; the server's copy is the fallback. */
const TEMPLATE_COPY = (): Record<string, { label: string; levels: string[] }> => ({
  area_unit: { label: t`Area and unit`, levels: [t`Area`, t`Unit`] },
  state_district_chapter: { label: t`State, district and chapter`, levels: [t`State`, t`District`, t`Chapter`] },
  branches: { label: t`Branches only`, levels: [t`Branch`] },
});

/**
 * Up to four named levels, top level first. A template only fills the draft; nothing is saved until
 * Save, and the server refuses removing a level a unit still sits on (`member_unit_levels_in_use`).
 * The parent keys this editor by the saved names, so a successful save starts a fresh draft.
 */
export function UnitLevelsEditor({ makerspaceId, levels, templates }: { makerspaceId: number; levels: string[]; templates: LevelTemplate[] }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState<string[]>(levels);
  const save = useMutation({
    mutationFn: () => unitsApi.setLevels(makerspaceId, draft.map(name => name.trim())),
    onSuccess: () => client.invalidateQueries({ queryKey: unitKeys.all(makerspaceId) }),
  });
  const copy = TEMPLATE_COPY();
  const dirty = draft.join("\u0000") !== levels.join("\u0000");
  const invalid = draft.some(name => !name.trim() || name.trim().length > 40);
  const set = (index: number, value: string) => { save.reset(); setDraft(draft.map((name, at) => (at === index ? value : name))); };
  return <section aria-labelledby="unit-levels-title" className="grid gap-3 rounded-xl border border-line p-4">
    <div className="grid gap-1">
      <h3 id="unit-levels-title" className="title-section">{t`Level names`}</h3>
      <p className="text-sm text-muted">{t`What your units are called at each level, top first. Members see these names when they join.`}</p>
    </div>
    <div className="flex flex-wrap gap-2" role="group" aria-label={t`Start from a template`}>
      {templates.map(template => <button key={template.key} type="button" className="desk-button min-h-11"
        onClick={() => { save.reset(); setDraft(copy[template.key]?.levels ?? template.levels); }}>
        {copy[template.key]?.label ?? template.label}</button>)}
    </div>
    <ol className="grid gap-2 sm:grid-cols-2">
      {draft.map((name, index) => <li key={index} className="flex items-end gap-2">
        <Field label={t`Level ${index + 1}`} className="min-w-0 flex-1">
          <input className="desk-input" maxLength={40} value={name} onChange={event => set(index, event.target.value)} />
        </Field>
        {index === draft.length - 1 ? <button type="button" className="desk-button min-h-11" aria-label={t`Remove level ${index + 1}`}
          onClick={() => { save.reset(); setDraft(draft.slice(0, -1)); }}>{t`Remove`}</button> : null}
      </li>)}
    </ol>
    {!draft.length ? <p className="text-sm text-muted">{t`No level names yet. Units can still nest up to four deep; naming levels makes the join page clearer.`}</p> : null}
    <div className="flex flex-wrap items-center gap-2">
      {draft.length < MAX_LEVELS ? <button type="button" className="desk-button min-h-11" onClick={() => { save.reset(); setDraft([...draft, ""]); }}>{t`Add a level`}</button> : null}
      <button type="button" className="desk-button-primary min-h-11" disabled={!dirty || invalid || save.isPending} onClick={() => save.mutate()}>
        {save.isPending ? t`Saving…` : t`Save level names`}</button>
      {dirty && invalid ? <span className="text-sm text-muted">{t`Give every level a name of up to 40 characters.`}</span> : null}
    </div>
    {save.error ? <ErrorText message={unitErrorText(save.error)} /> : null}
  </section>;
}

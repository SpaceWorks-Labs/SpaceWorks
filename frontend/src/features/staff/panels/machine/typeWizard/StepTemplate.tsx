import { plural, t } from "@lingui/core/macro";

import { LogoLoader } from "../../../../../components/LogoLoader";
import { Badge } from "../../../../../components/ui";
import type { TypeTemplate } from "./templatesApi";
import { useTemplates } from "./templatesApi";

export const BLANK = "__blank__";

/** Step 1: pick a catalogue template, or start blank. The pick is only remembered here; Basics applies it. */
export function StepTemplate({ makerspaceId, selected, onSelect, existing, applying, error }: {
  makerspaceId: number; selected: string | null; onSelect: (template: TypeTemplate | null) => void; existing: boolean; applying?: boolean; error?: string;
}) {
  const templates = useTemplates(makerspaceId);
  const rows = templates.data ?? [];
  const card = (key: string, title: string, body: string, pick: () => void, badge?: string) =>
    <li key={key}><button type="button" role="radio" aria-checked={selected === key} onClick={pick} disabled={applying}
      className={`grid min-h-24 w-full gap-1 rounded-xl border p-3 text-left ${selected === key ? "border-brand bg-surface" : "border-line bg-panel"}`}>
      <span className="flex flex-wrap items-center justify-between gap-2"><strong className="min-w-0 break-words">{title}</strong>{badge ? <Badge tone="info">{badge}</Badge> : null}</span>
      <span className="text-sm text-muted">{body}</span></button></li>;
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{existing
      ? t`Apply a template to add its consumables to this type. Rows the type already has are kept.`
      : t`A template pre-fills the consumables, intake fields and settings for a kind of machine. Everything stays editable. You can also start blank.`}</p>
    {templates.isLoading ? <LogoLoader label={t`Loading templates…`} size={48} className="min-h-16 py-3" /> : null}
    {templates.isError ? <p role="alert" className="text-sm text-danger">{templates.error.message}</p> : null}
    <ul role="radiogroup" aria-label={t`Templates`} className="grid gap-2 sm:grid-cols-2">
      {existing ? null : card(BLANK, t`Start blank`, t`An empty machine type. You add the consumables and settings yourself.`, () => onSelect(null))}
      {rows.map(row => card(row.key, row.name, row.description || `${plural(row.spec.consumables.length, { one: "# consumable", other: "# consumables" })}`,
        () => onSelect(row), row.customised ? t`Your copy` : row.is_builtin ? undefined : t`Custom`))}
    </ul>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
  </div>;
}

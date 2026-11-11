import { t } from "@lingui/core/macro";

import type { PlanLine } from "./eventEquipmentApi";

export type DefaultLines = Record<number, { name: string; quantity: number }>;
/** Per person: product id -> quantity. A product the person has not changed follows the default. */
export type LineOverrides = Record<number, Record<number, number>>;

/**
 * Decision 221(b): one person may carry different lines, for example a team lead holding the shared
 * units. The override still becomes that person's own request, so accountability stays per person.
 * Undefined means "use the default lines"; zero leaves an item out for this person.
 */
export function personLines(defaults: DefaultLines, override: Record<number, number> | undefined): PlanLine[] | undefined {
  if (!override) return undefined;
  return Object.entries(defaults)
    .map(([id, line]) => ({ product_id: Number(id), quantity: override[Number(id)] ?? line.quantity }))
    .filter((line) => line.quantity > 0);
}

export function PersonLinesOverride({ person, defaults, value, onChange }: {
  person: string; defaults: DefaultLines; value: Record<number, number> | undefined;
  onChange: (next: Record<number, number> | undefined) => void;
}) {
  const entries = Object.entries(defaults);
  if (!entries.length) return null;
  const empty = value !== undefined && !personLines(defaults, value)?.length;
  return <div className="grid gap-2 pl-7">
    <label className="flex min-h-11 items-center gap-2 text-sm text-muted">
      <input type="checkbox" checked={value !== undefined} onChange={(event) => onChange(event.target.checked ? {} : undefined)} />
      {t`Different items for ${person}`}</label>
    {value !== undefined ? <>
      <p className="text-sm text-muted">{t`Set 0 to leave an item out. These items are still lent to ${person} alone.`}</p>
      <ul className="grid gap-2 sm:grid-cols-2">{entries.map(([id, line]) => <li key={id}>
        <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm"><span className="[overflow-wrap:anywhere]">{line.name}</span>
          <input className="desk-input w-20" type="number" min={0} max={99} value={value[Number(id)] ?? line.quantity}
            aria-label={t`Quantity of ${line.name} for ${person}`} onChange={(event) => {
              const quantity = Math.min(99, Math.max(0, Math.trunc(Number(event.target.value) || 0)));
              onChange({ ...value, [Number(id)]: quantity });
            }} /></label>
      </li>)}</ul>
      {empty ? <p className="text-sm text-danger" role="alert">{t`Give ${person} at least one item, or turn off different items.`}</p> : null}
    </> : null}
  </div>;
}

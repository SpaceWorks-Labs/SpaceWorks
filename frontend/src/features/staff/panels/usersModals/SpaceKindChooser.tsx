import { t } from "@lingui/core/macro";
import { useId } from "react";
import type { SpaceKind } from "../../../../lib/spaceNoun";

const OPTIONS = (): { kind: SpaceKind; title: string; detail: string }[] => [
  { kind: "makerspace", title: t`Makerspace`,
    detail: t`A workshop that lends tools and runs machines. Starts with this deployment's default modules.` },
  { kind: "organization", title: t`Organization workspace`,
    detail: t`A club, society or company that runs events, memberships with ID cards and room bookings. Inventory and Machines start off; you can turn them on later.` },
];

/**
 * Decision 295: the kind is chosen once, at creation, and cannot be changed afterwards. It sets
 * the wording and the starting modules only; every module stays switchable later.
 */
export function SpaceKindChooser({ value, onChange }: { value: SpaceKind; onChange: (kind: SpaceKind) => void }) {
  const id = useId();
  return <fieldset className="grid gap-2" aria-describedby={`${id}-note`}>
    <legend className="mb-1 text-sm font-semibold text-ink">{t`What are you creating?`}</legend>
    <div className="grid gap-2 sm:grid-cols-2">
      {OPTIONS().map(option => <label key={option.kind}
        className="flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-line bg-panel p-4 text-sm has-checked:border-accent has-checked:bg-accent-soft">
        <input type="radio" className="mt-1 h-5 w-5 shrink-0 accent-brand" name={`${id}-kind`} value={option.kind}
          checked={value === option.kind} onChange={() => onChange(option.kind)} />
        <span className="grid gap-1"><span className="font-semibold text-ink">{option.title}</span>
          <span className="text-muted">{option.detail}</span></span>
      </label>)}
    </div>
    <p id={`${id}-note`} className="text-xs text-muted">{t`The kind can't be changed after the space is created.`}</p>
  </fieldset>;
}

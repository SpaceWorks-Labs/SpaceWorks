import { Icon, IconButton } from "../../../components/ui";
import type { StatsSectionKey } from "../api";

type Choice = { key: StatsSectionKey; label: string };

/**
 * Shown sections first in page order, then the hidden ones. Up/down buttons reorder the
 * shown ones (keyboard and screen-reader friendly, no drag needed); the checkbox shows or
 * hides a section, appending it at the end.
 */
export function SectionOrderList({ choices, value, disabled, onChange }: {
  choices: Choice[]; value: StatsSectionKey[]; disabled: boolean; onChange: (next: StatsSectionKey[]) => void;
}) {
  const labels = new Map(choices.map(choice => [choice.key, choice.label]));
  const hidden = choices.filter(choice => !value.includes(choice.key)).map(choice => choice.key);
  const move = (index: number, by: -1 | 1) => {
    const next = [...value];
    [next[index], next[index + by]] = [next[index + by], next[index]];
    onChange(next);
  };
  const toggle = (key: StatsSectionKey, on: boolean) => onChange(on ? [...value, key] : value.filter(item => item !== key));
  return <ol className="grid gap-2" aria-label="Sections in page order">
    {[...value, ...hidden].map(key => {
      const index = value.indexOf(key);
      const shown = index >= 0;
      const label = labels.get(key) ?? key;
      return <li key={key} className="flex min-h-11 flex-wrap items-center gap-3 rounded-xl border border-line bg-panel px-3 py-2">
        <label className="flex min-h-11 min-w-0 flex-1 items-center gap-3 text-sm font-semibold">
          <input type="checkbox" checked={shown} disabled={disabled} onChange={event => toggle(key, event.target.checked)} />
          <span className="min-w-0 break-words">{shown ? `${index + 1}. ` : ""}{label}</span>
          {shown ? null : <span className="text-xs font-normal text-muted">Hidden</span>}
        </label>
        {shown ? <span className="flex gap-1">
          <IconButton label={`Move ${label} up`} disabled={disabled || index === 0} onClick={() => move(index, -1)}>
            <Icon name="ArrowUp" className="h-5 w-5" /></IconButton>
          <IconButton label={`Move ${label} down`} disabled={disabled || index === value.length - 1} onClick={() => move(index, 1)}>
            <Icon name="ArrowDown" className="h-5 w-5" /></IconButton>
        </span> : null}
      </li>;
    })}
  </ol>;
}

import { rove } from "./useRovingFocus";
export type SegmentedControlProps = { label: string; value: string;
  options: { value: string; label: string }[]; onChange: (value: string) => void };
export function SegmentedControl({ label, value, options, onChange }: SegmentedControlProps) {
  const active = options.some(option => option.value === value) ? value : options[0]?.value;
  return <div role="radiogroup" aria-label={label} className="inline-flex max-w-full flex-wrap gap-1 rounded-control border border-line bg-surface p-1"
    onKeyDown={event => rove(event, '[role="radio"]', true)}>
    {options.map(option => <button key={option.value} type="button" role="radio"
      aria-checked={option.value === active} tabIndex={option.value === active ? 0 : -1}
      onClick={() => onChange(option.value)}
      className={`min-h-11 min-w-11 rounded-control border px-4 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${option.value === active ? "border-outline bg-panel text-ink" : "border-transparent text-muted hover:text-ink"}`}>
      {option.label}</button>)}
  </div>;
}

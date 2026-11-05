import { Plus, X } from "lucide-react";

/** A variant's options as key/value pairs (size: M, colour: red). Empty keys are dropped on save. */
export function ShopOptionsEditor({ label, value, onChange }: {
  label: string; value: [string, string][]; onChange: (next: [string, string][]) => void;
}) {
  const set = (index: number, part: 0 | 1, text: string) =>
    onChange(value.map((pair, at) => at === index ? (part === 0 ? [text, pair[1]] : [pair[0], text]) as [string, string] : pair));
  return <fieldset className="grid gap-2">
    <legend className="text-sm font-semibold text-ink">Options for {label}</legend>
    {value.map(([key, text], index) => <div key={index} className="flex flex-wrap items-end gap-2">
      <label className="grid gap-1 text-xs text-muted">Option
        <input className="desk-input min-h-11 w-32 text-sm" value={key} placeholder="size" onChange={event => set(index, 0, event.target.value)} /></label>
      <label className="grid gap-1 text-xs text-muted">Value
        <input className="desk-input min-h-11 w-32 text-sm" value={text} placeholder="M" onChange={event => set(index, 1, event.target.value)} /></label>
      <button type="button" className="desk-button-ghost min-h-11 min-w-11 px-0" aria-label={`Remove option ${key || index + 1} from ${label}`}
        onClick={() => onChange(value.filter((_, at) => at !== index))}><X aria-hidden="true" size={18} /></button>
    </div>)}
    <button type="button" className="desk-button min-h-11 justify-self-start" onClick={() => onChange([...value, ["", ""]])}>
      <Plus aria-hidden="true" size={18} />Add an option</button>
  </fieldset>;
}

export const toPairs = (options: unknown): [string, string][] =>
  options && typeof options === "object" ? Object.entries(options as Record<string, unknown>).map(([key, value]) => [key, String(value)]) : [];
export const fromPairs = (pairs: [string, string][]) =>
  Object.fromEntries(pairs.map(([key, value]) => [key.trim(), value.trim()]).filter(([key]) => key));

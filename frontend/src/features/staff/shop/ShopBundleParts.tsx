import { Plus, X } from "lucide-react";

export type BundlePart = { variant_id: number; quantity: number };
export type PartChoice = { id: number; label: string };

/** A kit's parts: selling the kit takes each part's stock (with bundle mode on). */
export function ShopBundleParts({ parts, choices, bundleMode, onBundleMode, onChange }: {
  parts: BundlePart[]; choices: PartChoice[]; bundleMode: boolean; onBundleMode: (on: boolean) => void; onChange: (parts: BundlePart[]) => void;
}) {
  const set = (index: number, patch: Partial<BundlePart>) => onChange(parts.map((part, at) => at === index ? { ...part, ...patch } : part));
  return <fieldset className="grid gap-3">
    <legend className="title-section mb-2">Kit parts</legend>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={bundleMode}
      onChange={event => onBundleMode(event.target.checked)} />Take each part's stock when this kit sells</label>
    {bundleMode ? <>
      {parts.map((part, index) => <div key={index} className="flex flex-wrap items-end gap-2">
        <label className="grid min-w-0 flex-1 basis-56 gap-1 text-sm font-semibold">Part
          <select className="desk-input min-h-11 font-normal" value={part.variant_id || ""} onChange={event => set(index, { variant_id: Number(event.target.value) })}>
            <option value="">Choose an item</option>
            {choices.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}</select></label>
        <label className="grid gap-1 text-sm font-semibold">Quantity<input className="desk-input min-h-11 w-24 font-normal" type="number" min={1}
          value={part.quantity} onChange={event => set(index, { quantity: Math.max(1, Number(event.target.value) || 1) })} /></label>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11 px-0" aria-label={`Remove part ${index + 1}`}
          onClick={() => onChange(parts.filter((_, at) => at !== index))}><X aria-hidden="true" size={18} /></button>
      </div>)}
      <button type="button" className="desk-button min-h-11 justify-self-start" onClick={() => onChange([...parts, { variant_id: 0, quantity: 1 }])}>
        <Plus aria-hidden="true" size={18} />Add a part</button>
    </> : null}
  </fieldset>;
}

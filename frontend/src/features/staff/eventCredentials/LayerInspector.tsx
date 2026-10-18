import type { Layer } from "./layout";
import { MERGE_TAGS } from "./layout";

export function LayerInspector({ layer, onChange }: { layer: Layer; onChange: (patch: Partial<Layer>) => void }) {
  return <fieldset className="grid gap-3 rounded-control border border-line p-3">
    <legend className="px-1 text-sm font-semibold text-ink">Layer appearance</legend>
    {layer.type === "text" ? <>
      <label className="grid gap-1 text-sm">Text<textarea className="desk-input" rows={3} maxLength={500} value={layer.text ?? ""}
        onChange={(event) => onChange({ text: event.target.value })} /></label>
      <div className="flex flex-wrap gap-2" aria-label="Insert merge tag">{MERGE_TAGS.map((tag) => <button key={tag} type="button" className="desk-button min-h-11"
        onClick={() => onChange({ text: (layer.text ?? "") + `{{${tag}}}` })}>{`{{${tag}}}`}</button>)}</div>
    </> : <p className="text-sm text-muted">{layer.type === "certificate_id" ? "The printed certificate ID is filled at issue time." : "This is a server-owned resource slot. Preview uses sample resources."}</p>}
    {layer.type === "text" || layer.type === "certificate_id" ? <>
      <label className="grid gap-1 text-sm">Font family<select className="desk-input" value={layer.font_family ?? "Gilroy"}
        onChange={(event) => onChange({ font_family: event.target.value as Layer["font_family"] })}><option>Gilroy</option><option>Unbounded</option></select></label>
      <label className="grid gap-1 text-sm">Weight<select className="desk-input" value={layer.font_weight ?? 400}
        onChange={(event) => onChange({ font_weight: Number(event.target.value) as Layer["font_weight"] })}>{[400, 500, 600, 700].map((value) => <option key={value}>{value}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Colour<select className="desk-input" value={layer.colour_token ?? "ink"}
        onChange={(event) => onChange({ colour_token: event.target.value })}>{["ink", "teal", "orange", "citron", "sky", "yellow", "cream"].map((value) => <option key={value}>{value}</option>)}</select></label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={layer.uppercase ?? false} onChange={(event) => onChange({ uppercase: event.target.checked })} />Uppercase</label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={layer.shrink_to_fit ?? true} onChange={(event) => onChange({ shrink_to_fit: event.target.checked })} />Shrink text to fit (minimum 6 pt)</label>
      <label className="grid gap-1 text-sm">Letter spacing (pt)<input className="desk-input" type="number" min={-1} max={8} step={0.1} value={layer.tracking_pt ?? 0} onChange={(event) => onChange({ tracking_pt: Number(event.target.value) })} /></label>
      <p className="text-xs text-muted">Italic is unavailable in the approved font kit.</p>
    </> : null}
    <label className="grid gap-1 text-sm">Rotation (degrees)<input className="desk-input" type="number" min={-360} max={360} value={layer.rotation} onChange={(event) => onChange({ rotation: Number(event.target.value) })} /></label>
    <label className="grid gap-1 text-sm">Opacity<input className="desk-input" type="number" min={0} max={1} step={0.1} value={layer.opacity ?? 1} onChange={(event) => onChange({ opacity: Number(event.target.value) })} /></label>
  </fieldset>;
}

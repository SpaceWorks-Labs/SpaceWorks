import { useEffect, useState } from "react";
import { COLOUR_TOKENS, layerColour, type Layer } from "../layout";
import { contrast } from "./geometry";

/** Brand colour presets plus a free #RRGGBB colour, with the WCAG contrast against white paper. */
export function ColourField({ layer, paperMeasurable, onChange }: { layer: Layer; paperMeasurable: boolean;
  onChange: (patch: Partial<Layer>) => void }) {
  const current = layerColour(layer);
  const [draft, setDraft] = useState(current);
  useEffect(() => setDraft(current), [current]);
  const ratio = contrast(current, "#FFFFFF");
  const valid = /^#[0-9A-Fa-f]{6}$/.test(draft);
  return <fieldset className="grid gap-2">
    <legend className="text-sm font-semibold text-ink">Colour</legend>
    <div className="flex flex-wrap gap-2" role="group" aria-label="Brand colour presets">
      {Object.entries(COLOUR_TOKENS).map(([token, hex]) => <button key={token} type="button"
        aria-label={`Use ${token}`} aria-pressed={!layer.colour && (layer.colour_token ?? "ink") === token}
        className="h-11 w-11 rounded-control border border-line focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus aria-pressed:ring-2 aria-pressed:ring-focus"
        style={{ background: hex }} onClick={() => onChange({ colour_token: token, colour: undefined })} />)}
    </div>
    <div className="flex flex-wrap items-end gap-2">
      <label className="grid gap-1 text-sm">Any colour<input type="color" className="h-11 w-16 rounded-control border border-line bg-surface" value={current}
        onChange={(event) => onChange({ colour: event.target.value.toUpperCase() })} /></label>
      <label className="grid min-w-0 flex-1 gap-1 text-sm">Hex code<input className="desk-input font-mono" value={draft} maxLength={7}
        aria-invalid={!valid} onChange={(event) => { setDraft(event.target.value); if (/^#[0-9A-Fa-f]{6}$/.test(event.target.value)) onChange({ colour: event.target.value.toUpperCase() }); }} /></label>
    </div>
    {!valid ? <p className="text-xs text-danger" role="alert">Use a hex code like #142C2A.</p> : null}
    {paperMeasurable ? <p className={`text-xs ${ratio < 4.5 ? "text-danger" : "text-muted"}`} role={ratio < 4.5 ? "alert" : undefined}>
      Contrast on white paper {ratio}:1{ratio < 4.5 ? ". Text needs at least 4.5:1 to stay readable; choose a darker colour." : ""}</p>
      : <p className="text-xs text-muted">A full-page picture sits behind this text, so check its contrast in the PDF preview.</p>}
  </fieldset>;
}

import { t } from "@lingui/core/macro";
import { AlignHorizontalJustifyCenter, AlignHorizontalJustifyEnd, AlignHorizontalJustifyStart, AlignVerticalJustifyCenter,
  AlignVerticalJustifyEnd, AlignVerticalJustifyStart } from "lucide-react";
import type { Layer } from "./layout";
import { CERTIFICATE_MERGE_TAGS, MERGE_TAGS } from "./layout";
import { ColourField } from "./designer/ColourField";
import type { Alignment } from "./designer/geometry";

const ALIGN: { how: Alignment; label: string; Icon: typeof AlignHorizontalJustifyStart }[] = [
  { how: "left", label: t`Align to page left`, Icon: AlignHorizontalJustifyStart },
  { how: "center", label: t`Centre on page horizontally`, Icon: AlignHorizontalJustifyCenter },
  { how: "right", label: t`Align to page right`, Icon: AlignHorizontalJustifyEnd },
  { how: "top", label: t`Align to page top`, Icon: AlignVerticalJustifyStart },
  { how: "middle", label: t`Centre on page vertically`, Icon: AlignVerticalJustifyCenter },
  { how: "bottom", label: t`Align to page bottom`, Icon: AlignVerticalJustifyEnd },
];

function NumberField({ label, value, min, max, step = 0.5, onChange }: { label: string; value: number; min: number; max: number;
  step?: number; onChange: (value: number) => void }) {
  return <label className="grid gap-1 text-sm">{label}<input className="desk-input" type="number" min={min} max={max} step={step}
    value={Math.round(value * 100) / 100} onChange={(event) => { const next = Number(event.target.value); if (Number.isFinite(next)) onChange(next); }} /></label>;
}

export function LayerInspector({ layer, onChange, onAlign, kind = "certificate", paperMeasurable = true }: {
  layer: Layer; onChange: (patch: Partial<Layer>) => void; onAlign: (how: Alignment) => void;
  kind?: "certificate" | "badge"; paperMeasurable?: boolean;
}) {
  const typed = layer.type === "text" || layer.type === "certificate_id" || layer.type === "signature";
  const tags = kind === "certificate" ? CERTIFICATE_MERGE_TAGS : MERGE_TAGS;
  return <fieldset className="grid gap-4 rounded-control border border-line p-3" disabled={layer.locked}>
    <legend className="px-1 text-sm font-semibold text-ink">{t`Selected layer`}{layer.locked ? t` (locked: unlock it in the layer list to edit)` : ""}</legend>
    <div className="flex flex-wrap gap-1" role="group" aria-label={t`Align to page`}>
      {ALIGN.map(({ how, label, Icon }) => <button key={how} type="button" className="desk-button min-h-11 min-w-11" aria-label={label} title={label}
        onClick={() => onAlign(how)}><Icon size={18} aria-hidden="true" /></button>)}
    </div>
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <NumberField label={t`X (mm)`} value={layer.x_mm} min={0} max={420} onChange={(x_mm) => onChange({ x_mm })} />
      <NumberField label={t`Y (mm)`} value={layer.y_mm} min={0} max={420} onChange={(y_mm) => onChange({ y_mm })} />
      <NumberField label={t`Width (mm)`} value={layer.width_mm} min={1} max={420} onChange={(width_mm) => onChange({ width_mm })} />
      <NumberField label={t`Height (mm)`} value={layer.height_mm} min={1} max={420} onChange={(height_mm) => onChange({ height_mm })} />
      <NumberField label={t`Rotation (°)`} value={layer.rotation} min={-180} max={180} step={layer.type.endsWith("qr") ? 90 : 1} onChange={(rotation) => onChange({ rotation })} />
      <NumberField label={t`Opacity`} value={layer.opacity ?? 1} min={0} max={1} step={0.05} onChange={(opacity) => onChange({ opacity })} />
    </div>
    {layer.type === "text" ? <>
      <label className="grid gap-1 text-sm">{t`Text`}<textarea className="desk-input" rows={3} maxLength={500} value={layer.text ?? ""}
        onChange={(event) => onChange({ text: event.target.value })} /></label>
      <div className="flex flex-wrap gap-2" role="group" aria-label={t`Insert merge tag`}>{tags.map((tag) => <button key={tag} type="button" className="desk-button min-h-11"
        onClick={() => onChange({ text: (layer.text ?? "") + `{{${tag}}}` })}>{`{{${tag}}}`}</button>)}</div>
    </> : null}
    {layer.type === "signature" ? <label className="grid gap-1 text-sm">{t`Signatory`}<select className="desk-input" value={layer.signature_slot ?? 1}
      onChange={(event) => onChange({ signature_slot: Number(event.target.value) as 1 | 2 | 3 })}>
      {[1, 2, 3].map((slot) => <option key={slot} value={slot}>{t`Signatory ${slot}`}</option>)}</select></label> : null}
    {layer.type === "certificate_id" ? <p className="text-sm text-muted">{t`Prints the certificate's serial, which anyone can check on the verification page.`}</p> : null}
    {!typed ? <p className="text-sm text-muted">{t`The server fills this picture or code at issue time; the PDF preview shows samples.`}</p> : null}
    {typed ? <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label className="grid gap-1 text-sm">{t`Font`}<select className="desk-input" value={layer.font_family ?? "Gilroy"}
          onChange={(event) => onChange({ font_family: event.target.value as Layer["font_family"] })}><option>{t`Gilroy`}</option><option>{t`Unbounded`}</option></select></label>
        <label className="grid gap-1 text-sm">{t`Weight`}<select className="desk-input" value={layer.font_weight ?? 400}
          onChange={(event) => onChange({ font_weight: Number(event.target.value) as Layer["font_weight"] })}>
          {[[400, "Regular"], [500, "Medium"], [600, "Semibold"], [700, "Bold"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <NumberField label={t`Size (pt)`} value={layer.font_size_pt ?? 12} min={6} max={96} onChange={(font_size_pt) => onChange({ font_size_pt })} />
        <NumberField label={t`Line height`} value={layer.line_height ?? 1.3} min={1} max={3} step={0.05} onChange={(line_height) => onChange({ line_height })} />
        <NumberField label={t`Letter spacing (pt)`} value={layer.tracking_pt ?? 0} min={-1} max={8} step={0.1} onChange={(tracking_pt) => onChange({ tracking_pt })} />
        <label className="grid gap-1 text-sm">{t`Text align`}<select className="desk-input" value={layer.align ?? "left"}
          onChange={(event) => onChange({ align: event.target.value as Layer["align"] })}><option value="left">{t`Left`}</option><option value="center">{t`Centre`}</option><option value="right">{t`Right`}</option></select></label>
      </div>
      <div className="flex flex-wrap gap-x-5">
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5" checked={layer.uppercase ?? false} onChange={(event) => onChange({ uppercase: event.target.checked })} />{t`Uppercase`}</label>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5" checked={layer.shrink_to_fit ?? true} onChange={(event) => onChange({ shrink_to_fit: event.target.checked })} />{t`Shrink to fit (down to 6 pt)`}</label>
        <label className="flex min-h-11 items-center gap-2 text-sm text-muted"><input type="checkbox" className="h-5 w-5" checked={false} disabled aria-describedby={`italic-${layer.id}`} />{t`Italic`}</label>
      </div>
      <p id={`italic-${layer.id}`} className="text-xs text-muted">{layer.font_family ?? t`Gilroy`} {t` has no true italic face in the approved font kit, so italic is off. Use weight or size for emphasis.`}</p>
      <ColourField layer={layer} paperMeasurable={paperMeasurable} onChange={onChange} />
    </> : null}
  </fieldset>;
}

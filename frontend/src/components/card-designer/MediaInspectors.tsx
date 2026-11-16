// Inspectors for the picture-like layers: photo (cut-out, sticker outline, masks, pan and zoom), image, shape,
// and the certificate pieces (signature, seal, serial).
import { t } from "@lingui/core/macro";

import type { Layer } from "./cardTypes";
import { ColourInput, NumberInput, SelectInput, Toggle } from "./inspectorFields";
import { FramingControls, MaskSelect, OutlineControls, ShadowControls } from "./StudioEffectControls";

type Props = { layer: Layer; disabled: boolean; onChange: (patch: Partial<Layer>) => void };
const maskOf = (shape: Layer["shape"]) => (shape === "circle" || shape === "arch" || shape === "rounded" ? shape : "none");

export function PhotoInspector({ layer, disabled, onChange }: Props) {
  return <div className="grid gap-3">
    <SelectInput label={t`Photo version`} value={layer.variant ?? "original"} disabled={disabled}
      options={[{ value: "original", label: t`Original photo` }, { value: "cutout", label: t`Cut-out (background removed)` },
        { value: "auto", label: t`Each holder's choice` }]}
      onChange={(variant) => onChange({ variant })} />
    {layer.variant === "cutout" ? <p className="text-xs text-muted">{t`A cut-out shows only for holders who have one; everyone else gets the original photo in the shape below.`}</p> : null}
    {layer.variant === "auto" ? <p className="text-xs text-muted">{t`The cut-out shows for holders who chose "Use cut-out"; everyone else gets the original photo in the shape below.`}</p> : null}
    <MaskSelect value={maskOf(layer.shape)} disabled={disabled}
      onChange={(mask) => onChange({ shape: mask === "none" ? "square" : mask })} />
    <SelectInput label={t`Photo look`} value={layer.filter ?? "none"} disabled={disabled}
      options={[{ value: "none", label: t`Original colours` }, { value: "grey", label: t`Black and white` },
        { value: "duotone", label: t`Duotone (two colours)` }]} onChange={(filter) => onChange({ filter })} />
    {layer.filter === "duotone" ? <div className="grid grid-cols-2 gap-2">
      <ColourInput label={t`Shadows`} value={layer.duotone_dark ?? "#142C2A"} disabled={disabled}
        onChange={(duotone_dark) => duotone_dark && onChange({ duotone_dark })} />
      <ColourInput label={t`Highlights`} value={layer.duotone_light ?? "#DFFF8F"} disabled={disabled}
        onChange={(duotone_light) => duotone_light && onChange({ duotone_light })} />
    </div> : null}
    <FramingControls zoom={layer.zoom} fx={layer.focal_x_pct} fy={layer.focal_y_pct} flip={layer.flip_x} disabled={disabled}
      onChange={(patch) => onChange(patch)} />
    <OutlineControls label={t`Sticker outline`} outline={layer.outline ?? null} disabled={disabled} onChange={(outline) => onChange({ outline })} />
    <ShadowControls shadow={layer.shadow ?? null} disabled={disabled} onChange={(shadow) => onChange({ shadow })} />
  </div>;
}

export function ImageInspector({ layer, disabled, onChange }: Props) {
  return <div className="grid gap-3">
    <SelectInput label={t`Fit`} value={layer.fit ?? "contain"} disabled={disabled}
      options={[{ value: "contain", label: t`Show the whole image` }, { value: "cover", label: t`Fill the box` },
        { value: "stretch", label: t`Stretch to the box` }]} onChange={(fit) => onChange({ fit })} />
    <MaskSelect value={layer.mask ?? "none"} disabled={disabled} onChange={(mask) => onChange({ mask })} />
    <FramingControls zoom={layer.zoom} fx={layer.focal_x_pct} fy={layer.focal_y_pct} flip={layer.flip_x} disabled={disabled}
      onChange={(patch) => onChange(patch)} />
    <Toggle label={t`Flip upside down`} checked={Boolean(layer.flip_y)} disabled={disabled} onChange={(flip_y) => onChange({ flip_y })} />
    <OutlineControls label={t`Outline`} outline={layer.outline ?? null} disabled={disabled} onChange={(outline) => onChange({ outline })} />
    <ShadowControls shadow={layer.shadow ?? null} disabled={disabled} onChange={(shadow) => onChange({ shadow })} />
  </div>;
}

export function ShapeInspector({ layer, disabled, onChange }: Props) {
  const gradient = layer.fill_gradient;
  const stroke = typeof layer.stroke === "string" ? layer.stroke : null;
  return <div className="grid gap-3">
    <SelectInput label={t`Shape`} value={layer.shape === "square" ? "rect" : layer.shape ?? "rect"} disabled={disabled}
      options={[{ value: "rect", label: t`Rectangle` }, { value: "rounded", label: t`Rounded rectangle` },
        { value: "circle", label: t`Circle` }, { value: "ellipse", label: t`Ellipse` }, { value: "arch", label: t`Arch` },
        { value: "line", label: t`Line` }, { value: "triangle", label: t`Triangle` }, { value: "diamond", label: t`Diamond` },
        { value: "hexagon", label: t`Hexagon` }, { value: "star", label: t`Star` }]} onChange={(shape) => onChange({ shape })} />
    <ColourInput label={t`Fill`} value={layer.fill} allowNone disabled={disabled} onChange={(fill) => onChange({ fill })} />
    <Toggle label={t`Gradient fill`} checked={Boolean(gradient)} disabled={disabled}
      onChange={(on) => onChange({ fill_gradient: on ? { type: "linear", angle_deg: 135, stops: [
        { colour: layer.fill ?? "#006E63", at: 0, alpha_pct: 100 }, { colour: "#142C2A", at: 100, alpha_pct: 100 }] } : null })} />
    {gradient ? <div className="grid grid-cols-2 gap-2">
      <ColourInput label={t`From`} value={gradient.stops[0].colour} disabled={disabled}
        onChange={(colour) => colour && onChange({ fill_gradient: { ...gradient, stops: [{ ...gradient.stops[0], colour }, ...gradient.stops.slice(1)] } })} />
      <ColourInput label={t`To`} value={gradient.stops[gradient.stops.length - 1].colour} disabled={disabled}
        onChange={(colour) => colour && onChange({ fill_gradient: { ...gradient, stops: [...gradient.stops.slice(0, -1), { ...gradient.stops[gradient.stops.length - 1], colour }] } })} />
      <NumberInput label={t`Angle`} unit="°" value={gradient.angle_deg} min={0} max={360} step={5} disabled={disabled}
        onChange={(angle_deg) => onChange({ fill_gradient: { ...gradient, angle_deg } })} />
    </div> : null}
    <ColourInput label={t`Outline`} value={stroke} allowNone disabled={disabled} onChange={(next) => onChange({ stroke: next })} />
    <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Outline width`} unit="mm" value={layer.stroke_mm ?? 0.3} min={0} max={5} step={0.1} disabled={disabled}
        onChange={(stroke_mm) => onChange({ stroke_mm })} />
      <NumberInput label={t`Corner radius`} unit="mm" value={layer.radius_mm ?? 0} min={0} max={20} disabled={disabled}
        onChange={(radius_mm) => onChange({ radius_mm })} />
    </div>
    <ShadowControls shadow={layer.shadow ?? null} disabled={disabled} onChange={(shadow) => onChange({ shadow })} />
  </div>;
}

export function CertificatePieceInspector({ layer, disabled, onChange }: Props) {
  if (layer.kind === "certificate_id") {
    return <SelectInput label={t`Number shown`} value={layer.format ?? "full"} disabled={disabled}
      options={[{ value: "full", label: t`Full serial number` }, { value: "short", label: t`Short (first 8 characters)` }]}
      onChange={(format) => onChange({ format })} />;
  }
  if (layer.kind === "seal") {
    return <div className="grid gap-3">
      <SelectInput label={t`Seal style`} value={layer.style ?? "ring"} disabled={disabled}
        options={[{ value: "ring", label: t`Ring` }, { value: "scallop", label: t`Scalloped rosette` }, { value: "star", label: t`Star` }]}
        onChange={(style) => onChange({ style })} />
      <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Label in the middle`}</span>
        <input className="desk-input min-h-11" maxLength={24} value={layer.label ?? ""} disabled={disabled}
          onChange={(event) => onChange({ label: event.target.value })} /></label>
      <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Text around the ring (Latin letters)`}</span>
        <input className="desk-input min-h-11" maxLength={40} value={layer.ring_text ?? ""} disabled={disabled}
          onChange={(event) => onChange({ ring_text: event.target.value })} /></label>
      <div className="grid grid-cols-2 gap-2">
        <ColourInput label={t`Fill`} value={layer.fill} disabled={disabled} onChange={(fill) => fill && onChange({ fill })} />
        <ColourInput label={t`Line`} value={typeof layer.stroke === "string" ? layer.stroke : "#142C2A"} disabled={disabled}
          onChange={(stroke) => stroke && onChange({ stroke })} />
      </div>
    </div>;
  }
  const row = layer.kind === "signature_row";
  const slots = layer.slots ?? [1, 2];
  return <div className="grid gap-3">
    {row ? <fieldset className="grid gap-1" disabled={disabled}><legend className="text-xs font-semibold text-muted">{t`Signatories shown`}</legend>
      <div className="flex gap-3">{[1, 2, 3].map((slot) => <Toggle key={slot} label={t`Signatory ${slot}`} checked={slots.includes(slot)} disabled={disabled}
        onChange={(on) => { const next = on ? [...slots, slot].sort() : slots.filter((item) => item !== slot); if (next.length) onChange({ slots: next }); }} />)}</div>
      <NumberInput label={t`Gap between signatures`} unit="mm" value={layer.gap_mm ?? 10} min={4} max={40} disabled={disabled}
        onChange={(gap_mm) => onChange({ gap_mm })} /></fieldset>
      : <SelectInput label={t`Signatory`} value={String(layer.signatory_slot ?? 1)} disabled={disabled}
        options={[1, 2, 3].map((slot) => ({ value: String(slot), label: t`Signatory ${slot}` }))}
        onChange={(slot) => onChange({ signatory_slot: Number(slot) })} />}
    <p className="text-xs text-muted">{t`Names and titles come from the event's signatories. A signatory who has not consented is left out and the rest are spaced evenly.`}</p>
    <div className="flex flex-wrap gap-x-4">
      <Toggle label={t`Signature image`} checked={layer.show_image !== false} disabled={disabled} onChange={(show_image) => onChange({ show_image })} />
      <Toggle label={t`Name`} checked={layer.show_name !== false} disabled={disabled} onChange={(show_name) => onChange({ show_name })} />
      <Toggle label={t`Title`} checked={layer.show_title !== false} disabled={disabled} onChange={(show_title) => onChange({ show_title })} />
      <Toggle label={t`Rule above the name`} checked={layer.rule !== null} disabled={disabled}
        onChange={(on) => onChange({ rule: on ? { colour: "#142C2A", width_pt: 0.6 } : null })} />
    </div>
    <ColourInput label={t`Text colour`} value={layer.colour} disabled={disabled} onChange={(colour) => colour && onChange({ colour })} />
  </div>;
}

// Small control groups the studio inspectors share: drop shadow, sticker outline and image framing.
import { t } from "@lingui/core/macro";

import type { Outline, Shadow } from "./cardTypes";
import { ColourInput, NumberInput, SelectInput, Toggle } from "./inspectorFields";

export const DEFAULT_SHADOW: Shadow = { dx_mm: 0.6, dy_mm: 0.8, blur_mm: 1.2, colour: "#000000", opacity_pct: 35 };

export function ShadowControls({ shadow, onChange, disabled, maxBlur = 6 }: {
  shadow: Shadow | null; onChange: (shadow: Shadow | null) => void; disabled?: boolean; maxBlur?: number;
}) {
  return <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={disabled}>
    <legend className="px-1 text-xs font-semibold text-muted">{t`Drop shadow`}</legend>
    <Toggle label={t`Add a shadow`} checked={Boolean(shadow)} onChange={(on) => onChange(on ? DEFAULT_SHADOW : null)} />
    {shadow ? <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Across`} unit="mm" value={shadow.dx_mm} min={-5} max={5} step={0.1} onChange={(dx_mm) => onChange({ ...shadow, dx_mm })} />
      <NumberInput label={t`Down`} unit="mm" value={shadow.dy_mm} min={-5} max={5} step={0.1} onChange={(dy_mm) => onChange({ ...shadow, dy_mm })} />
      <NumberInput label={t`Blur`} unit="mm" value={shadow.blur_mm} min={0} max={maxBlur} step={0.1} onChange={(blur_mm) => onChange({ ...shadow, blur_mm })} />
      <NumberInput label={t`Strength`} unit="%" value={shadow.opacity_pct} min={0} max={100} step={5} onChange={(opacity_pct) => onChange({ ...shadow, opacity_pct })} />
      <ColourInput label={t`Colour`} value={shadow.colour} onChange={(colour) => colour && onChange({ ...shadow, colour })} />
    </div> : null}
  </fieldset>;
}

export function OutlineControls({ outline, onChange, disabled, label }: {
  outline: Outline | null; onChange: (outline: Outline | null) => void; disabled?: boolean; label: string;
}) {
  return <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={disabled}>
    <legend className="px-1 text-xs font-semibold text-muted">{label}</legend>
    <Toggle label={t`Add a white outline`} checked={Boolean(outline)} onChange={(on) => onChange(on ? { width_mm: 1, colour: "#FFFFFF" } : null)} />
    {outline ? <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Width`} unit="mm" value={outline.width_mm} min={0.1} max={3} step={0.1} onChange={(width_mm) => onChange({ ...outline, width_mm })} />
      <ColourInput label={t`Colour`} value={outline.colour} onChange={(colour) => colour && onChange({ ...outline, colour })} />
    </div> : null}
  </fieldset>;
}

export function FramingControls({ zoom, fx, fy, flip, onChange, disabled }: {
  zoom?: number; fx?: number; fy?: number; flip?: boolean; disabled?: boolean;
  onChange: (patch: { zoom?: number; focal_x_pct?: number; focal_y_pct?: number; flip_x?: boolean }) => void;
}) {
  return <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={disabled}>
    <legend className="px-1 text-xs font-semibold text-muted">{t`Zoom and position inside the frame`}</legend>
    <div className="grid grid-cols-3 gap-2">
      <NumberInput label={t`Zoom`} unit="×" value={zoom ?? 1} min={1} max={4} step={0.1} onChange={(value) => onChange({ zoom: value })} />
      <NumberInput label={t`Left–right`} unit="%" value={fx ?? 50} min={0} max={100} step={5} onChange={(value) => onChange({ focal_x_pct: value })} />
      <NumberInput label={t`Up–down`} unit="%" value={fy ?? 50} min={0} max={100} step={5} onChange={(value) => onChange({ focal_y_pct: value })} />
    </div>
    <Toggle label={t`Mirror`} checked={Boolean(flip)} onChange={(flip_x) => onChange({ flip_x })} />
  </fieldset>;
}

export const MASK_OPTIONS = (): { value: "none" | "rounded" | "circle" | "arch"; label: string }[] => [
  { value: "none", label: t`Square corners` }, { value: "rounded", label: t`Rounded` },
  { value: "circle", label: t`Circle` }, { value: "arch", label: t`Arch` }];

export function MaskSelect({ value, onChange, disabled }: { value: "none" | "rounded" | "circle" | "arch"; disabled?: boolean;
  onChange: (value: "none" | "rounded" | "circle" | "arch") => void }) {
  return <SelectInput label={t`Shape`} value={value} disabled={disabled} options={MASK_OPTIONS()} onChange={onChange} />;
}

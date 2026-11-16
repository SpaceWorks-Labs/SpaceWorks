// Edit a gradient: linear or radial, angle or centre and radius, and 2 to 6 colour stops (overlays add per-stop alpha).
import { t } from "@lingui/core/macro";

import type { GradientSpec } from "./cardTypes";
import { ColourInput, NumberInput, SelectInput } from "./inspectorFields";

export const MAX_STOPS = 6;

export function GradientEditor({ value, onChange, readOnly, alpha }: {
  value: GradientSpec; onChange: (value: GradientSpec) => void; readOnly?: boolean; alpha?: boolean;
}) {
  const setStop = (index: number, patch: Partial<GradientSpec["stops"][number]>) =>
    onChange({ ...value, stops: value.stops.map((stop, i) => (i === index ? { ...stop, ...patch } : stop)) });
  return <div className="grid gap-2">
    <SelectInput label={t`Gradient type`} value={value.type} disabled={readOnly}
      options={[{ value: "linear", label: t`Linear` }, { value: "radial", label: t`Radial` }]}
      onChange={(type) => onChange({ ...value, type })} />
    {value.type === "linear"
      ? <NumberInput label={t`Angle`} unit="°" value={value.angle_deg} min={0} max={360} step={5} disabled={readOnly}
        onChange={(angle_deg) => onChange({ ...value, angle_deg })} />
      : <div className="grid grid-cols-3 gap-2">
        <NumberInput label={t`Centre across`} unit="%" value={value.cx_pct ?? 50} min={0} max={100} step={5} disabled={readOnly}
          onChange={(cx_pct) => onChange({ ...value, cx_pct })} />
        <NumberInput label={t`Centre down`} unit="%" value={value.cy_pct ?? 50} min={0} max={100} step={5} disabled={readOnly}
          onChange={(cy_pct) => onChange({ ...value, cy_pct })} />
        <NumberInput label={t`Radius`} unit="%" value={value.radius_pct ?? 100} min={10} max={300} step={10} disabled={readOnly}
          onChange={(radius_pct) => onChange({ ...value, radius_pct })} />
      </div>}
    {value.stops.map((stop, index) => <div key={index} className={`grid items-end gap-2 ${alpha ? "grid-cols-[1fr_4.5rem_4.5rem]" : "grid-cols-[1fr_5.5rem]"}`}>
      <ColourInput label={t`Stop ${index + 1}`} value={stop.colour} disabled={readOnly} onChange={(colour) => colour && setStop(index, { colour })} />
      <NumberInput label={t`At`} unit="%" value={stop.at} min={0} max={100} step={5} disabled={readOnly} onChange={(at) => setStop(index, { at })} />
      {alpha ? <NumberInput label={t`Opacity`} unit="%" value={stop.alpha_pct ?? 100} min={0} max={100} step={5} disabled={readOnly}
        onChange={(alpha_pct) => setStop(index, { alpha_pct })} /> : null}
    </div>)}
    <div className="flex flex-wrap gap-2">
      {value.stops.length < MAX_STOPS ? <button type="button" className="desk-button-ghost min-h-11" disabled={readOnly}
        onClick={() => onChange({ ...value, stops: [...value.stops, { colour: "#FFFFFF", at: 100, ...(alpha ? { alpha_pct: 100 } : {}) }] })}>{t`Add a stop`}</button> : null}
      {value.stops.length > 2 ? <button type="button" className="desk-button-ghost min-h-11" disabled={readOnly}
        onClick={() => onChange({ ...value, stops: value.stops.slice(0, -1) })}>{t`Remove the last stop`}</button> : null}
    </div>
  </div>;
}

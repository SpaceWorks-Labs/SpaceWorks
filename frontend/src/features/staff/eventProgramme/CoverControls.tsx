import { t } from "@lingui/core/macro";
import { useId, type ReactNode } from "react";
import { FlipHorizontal2, FlipVertical2, RotateCcw, RotateCw } from "lucide-react";
import { LOOK_ORDER, MAX_ZOOM, RANGES, SHAPE_ORDER, SHAPES, type CoverEdits, type CoverLook, type CoverShape } from "./coverMath";

const SHAPE_LABEL = (shape: CoverShape) => ({ banner: t`Event page banner`, wide: t`Wide`, square: t`Square` })[shape];
const LOOK_LABEL = (look: CoverLook) => ({ original: t`Original`, vivid: t`Vivid`, warm: t`Warm`, cool: t`Cool`, mono: t`Mono`, soft: t`Soft` })[look];

type Update = (patch: Partial<CoverEdits>) => void;

function Slider({ label, value, min, max, step = 1, text, onChange }: {
  label: string; value: number; min: number; max: number; step?: number; text: string; onChange: (value: number) => void;
}) {
  const id = useId();
  return <div className="grid gap-1">
    <div className="flex items-center justify-between gap-2 text-sm"><label htmlFor={id} className="font-semibold text-ink">{label}</label>
      <output htmlFor={id} className="tabular-nums text-muted">{text}</output></div>
    <input id={id} type="range" className="min-h-11 w-full accent-accent" min={min} max={max} step={step} value={value}
      aria-valuetext={text} onChange={event => onChange(Number(event.target.value))} />
  </div>;
}

function Choice<T extends string>({ legend, options, value, label, onChange, extra }: {
  legend: string; options: T[]; value: T; label: (option: T) => string; onChange: (value: T) => void; extra?: (option: T) => ReactNode;
}) {
  return <fieldset className="grid gap-2"><legend className="mb-1 text-sm font-semibold text-ink">{legend}</legend>
    <div className="flex flex-wrap gap-2">{options.map(option => <label key={option}
      className="flex min-h-11 cursor-pointer items-center gap-2 rounded-control border border-line px-3 text-sm has-checked:border-brand-boundary has-checked:bg-brand-soft has-focus-visible:outline-2 has-focus-visible:outline-focus">
      <input type="radio" className="sr-only" checked={value === option} onChange={() => onChange(option)} />
      <span className="font-semibold">{label(option)}</span>{extra?.(option)}
    </label>)}</div>
  </fieldset>;
}

const signed = (value: number) => (value > 0 ? `+${value}` : String(value));

/** Shape, zoom, rotation, straightening and flips: everything that changes what the frame shows. */
export function CoverCropControls({ edits, update }: { edits: CoverEdits; update: Update }) {
  const turn = (by: number) => update({ rotation: (((edits.rotation + by) % 360) + 360) % 360, panX: 0, panY: 0 });
  return <div className="grid gap-4">
    <Choice legend={t`Shape`} options={SHAPE_ORDER} value={edits.shape} label={SHAPE_LABEL} onChange={shape => update({ shape, panX: 0, panY: 0 })}
      extra={shape => <span className="tabular-nums text-xs text-muted">{SHAPES[shape].ratio}{shape === "banner" ? t` · best` : ""}</span>} />
    <Slider label={t`Zoom`} value={edits.zoom} min={1} max={MAX_ZOOM} step={0.01} text={`${Math.round(edits.zoom * 100)}%`} onChange={zoom => update({ zoom })} />
    <Slider label={t`Straighten`} value={edits.straighten} min={RANGES.straighten[0]} max={RANGES.straighten[1]} step={0.5}
      text={t`${edits.straighten}°`} onChange={straighten => update({ straighten })} />
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button" onClick={() => turn(-90)}><RotateCcw size={18} aria-hidden="true" />{t`Rotate left`}</button>
      <button type="button" className="desk-button" onClick={() => turn(90)}><RotateCw size={18} aria-hidden="true" />{t`Rotate right`}</button>
      <button type="button" className="desk-button" aria-pressed={edits.flipX} onClick={() => update({ flipX: !edits.flipX })}><FlipHorizontal2 size={18} aria-hidden="true" />{t`Flip horizontally`}</button>
      <button type="button" className="desk-button" aria-pressed={edits.flipY} onClick={() => update({ flipY: !edits.flipY })}><FlipVertical2 size={18} aria-hidden="true" />{t`Flip vertically`}</button>
    </div>
  </div>;
}

/** A preset look, then brightness, contrast and saturation on top. */
export function CoverAdjustControls({ edits, update }: { edits: CoverEdits; update: Update }) {
  const changed = edits.look !== "original" || edits.brightness || edits.contrast || edits.saturation;
  return <div className="grid gap-4">
    <Choice legend={t`Look`} options={LOOK_ORDER} value={edits.look} label={LOOK_LABEL} onChange={look => update({ look })} />
    <Slider label={t`Brightness`} value={edits.brightness} min={RANGES.brightness[0]} max={RANGES.brightness[1]} text={signed(edits.brightness)} onChange={brightness => update({ brightness })} />
    <Slider label={t`Contrast`} value={edits.contrast} min={RANGES.contrast[0]} max={RANGES.contrast[1]} text={signed(edits.contrast)} onChange={contrast => update({ contrast })} />
    <Slider label={t`Saturation`} value={edits.saturation} min={RANGES.saturation[0]} max={RANGES.saturation[1]} text={signed(edits.saturation)} onChange={saturation => update({ saturation })} />
    <button type="button" className="desk-button justify-self-start" disabled={!changed}
      onClick={() => update({ look: "original", brightness: 0, contrast: 0, saturation: 0 })}>{t`Reset colour`}</button>
  </div>;
}

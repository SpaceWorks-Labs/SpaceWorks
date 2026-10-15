import { useState } from "react";

import { layoutFits, snapMillimetres, type PositionedElement } from "./positionedLayout";

type Props = {
  widthMm: number; heightMm: number; gridMm: number; elements: PositionedElement[];
  onChange: (elements: PositionedElement[]) => void;
  onGridChange?: (grid: number) => void;
  labels?: Record<string, string>; disabled?: boolean;
};

/** Shared by domain designers. The server PDF remains the authoritative font/overflow preview. */
export function PositionedLayoutEditor({ widthMm, heightMm, gridMm, elements, onChange,
  onGridChange, labels = {}, disabled = false }: Props) {
  const [selected, setSelected] = useState(0);
  const index = Math.min(selected, Math.max(0, elements.length - 1));
  const current = elements[index];
  const update = (patch: Partial<PositionedElement>) => onChange(elements.map((item, i) => i === index ? { ...item, ...patch } : item));
  const geometry = (key: "x_mm" | "y_mm" | "width_mm" | "height_mm", value: number) => {
    if (!current || !Number.isFinite(value)) return;
    const max = key === "x_mm" ? widthMm - current.width_mm : key === "y_mm" ? heightMm - current.height_mm
      : key === "width_mm" ? widthMm - current.x_mm : heightMm - current.y_mm;
    update({ [key]: snapMillimetres(value, gridMm, max, key === "width_mm" || key === "height_mm" ? Math.min(1, max) : 0) });
  };
  return <fieldset className="mt-3 grid gap-3" disabled={disabled}>
    <legend className="font-semibold text-ink">Positioned layout</legend>
    <p className="text-xs text-muted">Positions start at the top-left. Numeric controls snap to the grid; use arrow keys to move by one grid step. PDF preview checks the final text layout.</p>
    {onGridChange ? <label className="grid gap-1 text-sm">Grid (mm)<input className="desk-input" type="number" min="0.5" max="10" step="0.5" value={gridMm} onChange={(event) => {
      const next = Number(event.target.value); if (next >= 0.5 && next <= 10) onGridChange(next);
    }} /></label> : null}
    <div role="img" aria-label={`Layout preview, ${widthMm} by ${heightMm} millimetres. Select an element below to edit.`}
      className="relative w-full overflow-hidden border border-line bg-surface"
      style={{ aspectRatio: `${Math.max(1, widthMm)} / ${Math.max(1, heightMm)}`,
        backgroundSize: `${gridMm / widthMm * 100}% ${gridMm / heightMm * 100}%`,
        backgroundImage: "linear-gradient(to right, var(--color-line) 1px, transparent 1px), linear-gradient(to bottom, var(--color-line) 1px, transparent 1px)" }}>
      {elements.map((item, i) => <div key={item.field} aria-hidden="true" className={`absolute overflow-hidden border ${index === i ? "border-primary" : "border-line"}`}
        style={{ left: `${item.x_mm / widthMm * 100}%`, top: `${item.y_mm / heightMm * 100}%`,
          width: `${item.width_mm / widthMm * 100}%`, height: `${item.height_mm / heightMm * 100}%`,
          fontFamily: item.font === "serif" ? "serif" : "sans-serif", fontWeight: item.bold ? 700 : 400,
          textAlign: item.align, color: item.colour, fontSize: `${item.font_size_pt}px` }}>
        {labels[item.field] ?? item.field}
      </div>)}
    </div>
    {current ? <>
      <label className="grid gap-1 text-sm">Element<select className="desk-input" value={index} onChange={(event) => setSelected(Number(event.target.value))}>
        {elements.map((item, i) => <option key={item.field} value={i}>{labels[item.field] ?? item.field}</option>)}
      </select></label>
      <div className="grid grid-cols-2 gap-3">
        {([["x_mm", "Left"], ["y_mm", "Top"], ["width_mm", "Width"], ["height_mm", "Height"]] as const).map(([key, label]) =>
          <label key={key} className="grid gap-1 text-sm">{label} (mm)<input className="desk-input" type="number" step={gridMm}
            min={key === "width_mm" || key === "height_mm" ? 1 : 0} max={key === "x_mm" || key === "width_mm" ? widthMm : heightMm}
            value={current[key]} onChange={(event) => geometry(key, Number(event.target.value))} /></label>)}
        <label className="grid gap-1 text-sm">Font<select className="desk-input" value={current.font} onChange={(event) => update({ font: event.target.value as PositionedElement["font"] })}>
          <option value="sans">Sans</option><option value="serif">Serif</option>
        </select></label>
        <label className="grid gap-1 text-sm">Font size (pt)<input className="desk-input" type="number" min="6" max="48" value={current.font_size_pt} onChange={(event) => {
          const value = Number(event.target.value); if (value >= 6 && value <= 48) update({ font_size_pt: value });
        }} /></label>
        <label className="grid gap-1 text-sm">Alignment<select className="desk-input" value={current.align} onChange={(event) => update({ align: event.target.value as PositionedElement["align"] })}>
          <option value="left">Left</option><option value="center">Centre</option><option value="right">Right</option>
        </select></label>
        <label className="grid gap-1 text-sm">Text colour<input className="desk-input h-10 w-full" type="color" value={current.colour} onChange={(event) => update({ colour: event.target.value })} /></label>
      </div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={current.bold} onChange={(event) => update({ bold: event.target.checked })} />Bold</label>
    </> : null}
    {!layoutFits(elements, widthMm, heightMm) ? <p role="alert" className="text-sm text-danger">An element extends outside the printable area. Adjust its position or size before saving.</p> : null}
  </fieldset>;
}

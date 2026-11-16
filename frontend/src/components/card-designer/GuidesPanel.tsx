// Guides: bleed, safe zone, printer margin, punch slot and custom rulers. Shown in the editor only; nothing here is printed.
import { t } from "@lingui/core/macro";

import type { CardDocument, Guides, SideName } from "./cardTypes";
import { guidesOf, newPunchSlot } from "./GuidesOverlay";
import { customLimits, stocksFor } from "./cardGeometry";
import { applyStock } from "./designDocument";
import { NumberInput, SelectInput } from "./inspectorFields";

export function GuidesPanel({ document, sideName, update, readOnly }: {
  document: CardDocument; sideName: SideName; readOnly: boolean;
  update: (change: (current: CardDocument) => CardDocument) => void;
}) {
  const guides = guidesOf(document.guides);
  const width = document[sideName].page_width_mm;
  const certificate = document.kind === "certificate";
  const set = (patch: Partial<Guides>) => update((current) => ({ ...current, version: 3, guides: { ...guidesOf(current.guides), ...patch } }));
  const slot = guides.punch_slot;
  const custom = document.stock === "custom";
  const limits = customLimits(document.kind);
  return <div className="grid gap-3">
    <SelectInput label={document.kind === "certificate" ? t`Paper` : t`Card size`} value={document.stock} disabled={readOnly}
      options={stocksFor(document.kind).map((stock) => ({ value: stock.key, label: stock.label }))}
      onChange={(stock) => update((current) => applyStock(current, stock))} />
    {custom ? <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Width`} unit="mm" value={document.page_width_mm ?? document.front.page_width_mm} min={limits.min} max={limits.max} disabled={readOnly}
        onChange={(w) => update((current) => applyStock(current, "custom", w, current.front.page_height_mm))} />
      <NumberInput label={t`Height`} unit="mm" value={document.page_height_mm ?? document.front.page_height_mm} min={limits.min} max={limits.max} disabled={readOnly}
        onChange={(h) => update((current) => applyStock(current, "custom", current.front.page_width_mm, h))} />
    </div> : null}
    <p className="text-xs text-muted">{t`Guides help you place things. They are shown here only and never printed.`}</p>
    <div className="grid grid-cols-3 gap-2">
      <NumberInput label={t`Bleed`} unit="mm" value={guides.bleed_mm} min={0} max={5} step={0.5} disabled={readOnly} onChange={(bleed_mm) => set({ bleed_mm })} />
      <NumberInput label={t`Safe zone`} unit="mm" value={guides.safe_mm} min={0} max={15} step={0.5} disabled={readOnly} onChange={(safe_mm) => set({ safe_mm })} />
      <NumberInput label={certificate ? t`Print margin` : t`Printer margin`} unit="mm" value={guides.margin_mm} min={0} max={30} step={0.5}
        disabled={readOnly} onChange={(margin_mm) => set({ margin_mm })} />
    </div>
    <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={readOnly}>
      <legend className="px-1 text-xs font-semibold text-muted">{t`Punch hole for a lanyard`}</legend>
      <SelectInput label={t`Shape`} value={slot?.shape ?? "none"}
        options={[{ value: "none", label: t`None` }, { value: "slot", label: t`Slot (12 × 3 mm)` }, { value: "round", label: t`Round (5 mm)` }]}
        onChange={(shape) => set({ punch_slot: shape === "none" ? null : { ...newPunchSlot(shape, width), side: slot?.side ?? "both" } })} />
      {slot ? <>
        <div className="grid grid-cols-2 gap-2">
          <NumberInput label={t`Left`} unit="mm" value={slot.x_mm} min={0} max={width} step={0.5} onChange={(x_mm) => set({ punch_slot: { ...slot, x_mm } })} />
          <NumberInput label={t`Top`} unit="mm" value={slot.y_mm} min={0} max={document[sideName].page_height_mm} step={0.5}
            onChange={(y_mm) => set({ punch_slot: { ...slot, y_mm } })} />
        </div>
        <SelectInput label={t`Shown on`} value={slot.side} options={[{ value: "both", label: t`Both sides` }, { value: "front", label: t`Front` }, { value: "back", label: t`Back` }]}
          onChange={(side) => set({ punch_slot: { ...slot, side } })} />
      </> : null}
    </fieldset>
    <fieldset className="grid gap-2 rounded-control border border-line p-2" disabled={readOnly}>
      <legend className="px-1 text-xs font-semibold text-muted">{t`Ruler lines`}</legend>
      {guides.rulers.map((ruler, index) => <div key={index} className="grid grid-cols-[6rem_1fr_auto] items-end gap-2">
        <SelectInput label={t`Direction`} value={ruler.axis} options={[{ value: "x", label: t`Vertical` }, { value: "y", label: t`Horizontal` }]}
          onChange={(axis) => set({ rulers: guides.rulers.map((item, i) => (i === index ? { ...item, axis } : item)) })} />
        <NumberInput label={t`Position`} unit="mm" value={ruler.at_mm} min={0} max={Math.max(width, document[sideName].page_height_mm)} step={0.5}
          onChange={(at_mm) => set({ rulers: guides.rulers.map((item, i) => (i === index ? { ...item, at_mm } : item)) })} />
        <button type="button" className="desk-button-ghost min-h-11" onClick={() => set({ rulers: guides.rulers.filter((_item, i) => i !== index) })}>{t`Remove`}</button>
      </div>)}
      {guides.rulers.length < 20 ? <button type="button" className="desk-button min-h-11 justify-self-start"
        onClick={() => set({ rulers: [...guides.rulers, { axis: "x", at_mm: Math.round(width / 2) }] })}>{t`Add a ruler line`}</button> : null}
    </fieldset>
  </div>;
}

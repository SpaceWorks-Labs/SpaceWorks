// QUICK mode: the few choices most people need, without the canvas. Style (templates), colours, paper and
// orientation, what is shown, data fields, logo and background images. Everything is still the same document.
import { t } from "@lingui/core/macro";
import { RotateCw } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { CardDocument, CardDomain, Layer, SideName } from "./cardTypes";
import { UploadButton } from "./BackgroundPicker";
import { fieldsFor } from "./dataFields";
import { applyStock, layerName, newLayer, withSide } from "./designDocument";
import { stocksFor } from "./cardGeometry";
import { ColourInput, SelectInput, Toggle } from "./inspectorFields";
import { brandSwatches, quickItems, setAccentColour, setBackgroundColour, setTextColour, turnPaper } from "./quickEdits";
import type { DesignerEditing } from "./useDesignerEditing";

type Update = (change: (current: CardDocument) => CardDocument) => void;

function Swatches({ label, value, onPick, disabled }: { label: string; value?: string | null; onPick: (hex: string) => void; disabled: boolean }) {
  return <fieldset className="grid gap-1" disabled={disabled}>
    <legend className="text-xs font-semibold text-muted">{label}</legend>
    <div className="flex flex-wrap gap-1.5">
      {brandSwatches().map((swatch) => <button key={swatch.key} type="button" aria-pressed={value?.toUpperCase() === swatch.hex}
        aria-label={`${label}: ${swatch.label}`} title={swatch.label} onClick={() => onPick(swatch.hex)}
        className={`h-11 w-11 rounded-full border-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${value?.toUpperCase() === swatch.hex ? "border-accent-ink" : "border-line"}`}
        style={{ background: swatch.hex }} />)}
    </div>
    <ColourInput label={t`Custom ${label}`} value={value ?? "#FFFFFF"} disabled={disabled} onChange={(hex) => hex && onPick(hex)} />
  </fieldset>;
}

export function QuickPanel({ document, sideName, domain, designId, editing, update, templates, onAssetColour, answerFields }: {
  document: CardDocument; sideName: SideName; domain: CardDomain; designId: number; editing: DesignerEditing; update: Update;
  templates: ReactNode; onAssetColour: (assetId: string, colour: string) => void; answerFields?: { key: string; label: string }[];
}) {
  const side = document[sideName];
  const readOnly = !editing.canEdit;
  const [field, setField] = useState("name");
  const background = side.background.kind === "colour" ? side.background.colour : null;
  const textColour = side.layers.find((layer) => layer.kind === "text" || layer.kind === "data_field")?.colour;
  const accent = side.layers.find((layer) => layer.kind === "band" || layer.kind === "shape")?.fill;
  const items = quickItems(side.layers);
  const setHidden = (layer: Layer, hidden: boolean) => editing.patchOne(layer.id, { hidden });
  return <div className="grid gap-5" aria-label={t`Quick design`}>
    <section className="grid gap-2"><h3 className="text-sm font-semibold text-ink">{t`Style`}</h3>
      <p className="text-xs text-muted">{t`Start from a ready-made look, then adjust the rest here.`}</p>{templates}</section>
    <section className="grid gap-3"><h3 className="text-sm font-semibold text-ink">{t`Colours`}</h3>
      <Swatches label={t`Background`} value={background} disabled={readOnly}
        onPick={(hex) => update((current) => setBackgroundColour(current, sideName, hex))} />
      <Swatches label={t`Text`} value={textColour} disabled={readOnly}
        onPick={(hex) => update((current) => setTextColour(current, sideName, hex))} />
      <Swatches label={t`Accent bands and shapes`} value={accent} disabled={readOnly}
        onPick={(hex) => update((current) => setAccentColour(current, sideName, hex))} />
    </section>
    <section className="grid gap-2"><h3 className="text-sm font-semibold text-ink">{t`Paper and orientation`}</h3>
      <SelectInput label={t`Size`} value={document.stock} disabled={readOnly}
        options={stocksFor(document.kind).map((stock) => ({ value: stock.key, label: stock.label }))}
        onChange={(stock) => update((current) => applyStock(current, stock))} />
      <button type="button" className="desk-button min-h-11 justify-self-start" disabled={readOnly}
        onClick={() => update((current) => turnPaper(current))}><RotateCw size={16} aria-hidden="true" /> {t` Turn the card sideways`}</button>
    </section>
    <section className="grid gap-1"><h3 className="text-sm font-semibold text-ink">{t`What is shown`}</h3>
      {items.length ? items.map((layer) => <Toggle key={layer.id} label={layerName(layer)} checked={!layer.hidden} disabled={readOnly}
        onChange={(shown) => setHidden(layer, !shown)} />) : <p className="text-sm text-muted">{t`Nothing on this side yet.`}</p>}
    </section>
    <section className="grid gap-2"><h3 className="text-sm font-semibold text-ink">{t`Data fields`}</h3>
      <SelectInput label={t`Field`} value={field} disabled={readOnly} onChange={setField}
        options={fieldsFor(answerFields, domain).map((item) => ({ value: item.key, label: item.label }))} />
      <button type="button" className="desk-button min-h-11 justify-self-start" disabled={readOnly}
        onClick={() => editing.add(newLayer("data_field", side, document.stock, { field, text: `{{${field}}}` }))}>{t`Add this field`}</button>
    </section>
    <section className="grid gap-2"><h3 className="text-sm font-semibold text-ink">{t`Logo and background`}</h3>
      <UploadButton designId={designId} kind="image" label={t`Add a logo or picture`} disabled={readOnly}
        onUploaded={(asset_id, mean) => { onAssetColour(asset_id, mean); editing.add(newLayer("image", side, document.stock, { asset_id })); }} />
      <UploadButton designId={designId} kind="background" label={t`Use a background picture`} disabled={readOnly}
        onUploaded={(asset_id, mean) => { onAssetColour(asset_id, mean);
          update((current) => withSide(current, sideName, (value) => ({ ...value, background: { kind: "image", asset_id, fit: "cover", dim_pct: 0, fallback: mean } }))); }} />
    </section>
  </div>;
}

// The barcode layer's settings: what it carries, the symbology (decision 345(c)) and the readable line. Changing the
// symbology grows the box to that symbology's minimum (square for Data Matrix and Aztec) so scanners can read it.
import { t } from "@lingui/core/macro";

import type { Layer, Side } from "./cardTypes";
import { barcodeMinimum, carriesDesk, isMatrixCode, SYMBOLOGIES, symbologyLabel, symbologyOf, type Symbology } from "./barcodes";
import { SelectInput, Toggle } from "./inspectorFields";

export function resizedFor(layer: Layer, side: Side, symbology: Symbology, source: Layer["source"]): Partial<Layer> {
  const min = barcodeMinimum(symbology, source);
  const square = symbology === "datamatrix" || symbology === "aztec";
  let w = Math.max(layer.w_mm, min.w), h = Math.max(layer.h_mm, min.h);
  if (square) w = h = Math.max(min.w, min.h, Math.min(w, h));
  w = Math.min(w, side.page_width_mm - layer.x_mm); h = Math.min(h, side.page_height_mm - layer.y_mm);
  return { symbology: symbology === "code128" ? undefined : symbology, source, w_mm: w, h_mm: h };
}

export function BarcodeInspector({ layer, side, disabled, onChange }: {
  layer: Layer; side: Side; disabled: boolean; onChange: (patch: Partial<Layer>) => void;
}) {
  const symbology = symbologyOf(layer);
  const source = layer.source === "desk" ? "desk" : "number";
  const min = barcodeMinimum(symbology, source);
  return <div className="grid gap-2">
    <SelectInput label={t`Barcode carries`} value={source} disabled={disabled}
      options={[{ value: "number", label: t`The card number` },
        ...(carriesDesk(symbology) ? [{ value: "desk", label: t`The desk code (USB scanners)` }] : [])]}
      onChange={(next) => onChange(resizedFor(layer, side, symbology, next as Layer["source"]))} />
    <SelectInput label={t`Type`} value={symbology} disabled={disabled}
      options={SYMBOLOGIES.map((value) => ({ value, label: symbologyLabel(value) }))}
      onChange={(next) => onChange(resizedFor(layer, side, next as Symbology, carriesDesk(next as Symbology) ? source : "number"))} />
    {isMatrixCode(symbology) ? null : <Toggle label={t`Print the code under the bars`} checked={layer.show_text !== false}
      disabled={disabled} onChange={(show_text) => onChange({ show_text })} />}
    <p className="text-xs text-muted">{t`Black on a white plate. It needs at least ${min.w} × ${min.h} mm so a scanner reads it.`}
      {source === "desk" ? t` The desk code is the same private code as the desk QR, for barcode scanners at the desk.` : ""}
      {symbology === "ean13" || symbology === "upca" ? t` Card numbers that are not all digits print nothing in this type.` : ""}
      {min.w > side.page_width_mm - 6 ? t` This card is too narrow for it: use a landscape or larger card.` : ""}</p>
  </div>;
}

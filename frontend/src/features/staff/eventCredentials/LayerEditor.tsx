import { useState } from "react";
import { Copy, ArrowUp, ArrowDown, Trash2, Undo2, Plus } from "lucide-react";
import { PositionedLayoutEditor } from "../../../components/print-layout/PositionedLayoutEditor";
import type { PositionedElement } from "../../../components/print-layout/positionedLayout";
import { duplicate, newTextLayer, reorder, type Layer, type LayerDocument } from "./layout";
import { LayerInspector } from "./LayerInspector";
import { LayerCanvas } from "./LayerCanvas";

export function LayerEditor({ document, onChange, disabled = false, kind = "certificate" }: {
  document: LayerDocument; onChange: (value: LayerDocument) => void; disabled?: boolean; kind?: "certificate" | "badge";
}) {
  const [selected, setSelected] = useState(document.layers[0]?.id);
  const [history, setHistory] = useState<LayerDocument[]>([]);
  const [grid, setGrid] = useState(1);
  const current = document.layers.find((layer) => layer.id === selected) ?? document.layers[0];
  function change(layers: Layer[]) {
    setHistory((rows) => [...rows.slice(-29), document]);
    onChange({ ...document, layers });
  }
  function patch(value: Partial<Layer>) { change(document.layers.map((row) => row.id === current.id ? { ...row, ...value } : row)); }
  function add(type: Layer["type"]) {
    const layer = newTextLayer(document.layers.length);
    const slots = { logo: "logo", certificate_qr: "certificate_verification_qr", event_credential_qr: "event_credential_qr", photo: "selected_member_photo" };
    const next: Layer = type === "text" ? layer : { id: layer.id, order: layer.order, type,
      x_mm: 10, y_mm: 10, width_mm: 25, height_mm: 25, rotation: 0,
      ...(type in slots ? { resource_slot: slots[type as keyof typeof slots] } : {}) };
    change([...document.layers, next]); setSelected(next.id);
  }
  const positioned: PositionedElement[] = document.layers.map((row) => ({ field: row.id, x_mm: row.x_mm, y_mm: row.y_mm,
    width_mm: row.width_mm, height_mm: row.height_mm, font: "sans", font_size_pt: row.font_size_pt ?? 12,
    bold: (row.font_weight ?? 400) >= 600, align: row.align ?? "left", colour: "#142C2A" }));
  const addTypes: Layer["type"][] = kind === "badge" ? ["text", "logo", "photo", "event_credential_qr"] : ["text", "logo", "certificate_qr", "certificate_id"];
  return <fieldset className="grid min-w-0 gap-4" disabled={disabled}>
    <legend className="font-semibold text-ink">Layers ({document.layers.length}/20)</legend>
    <p className="text-sm text-muted">Canvas is approximate. The server PDF preview checks final fonts, wrapping and image placement.</p>
    <div className="flex flex-wrap gap-2"><button type="button" className="desk-button" disabled={!history.length} onClick={() => {
      const prior = history.at(-1); if (prior) { onChange(prior); setHistory(history.slice(0, -1)); }
    }}><Undo2 size={16} aria-hidden="true" />Undo</button>
      {addTypes.map((type) => <button className="desk-button" key={type} type="button" disabled={document.layers.length >= 20} onClick={() => add(type)}><Plus size={16} aria-hidden="true" />Add {type.replace(/_/g, " ")}</button>)}</div>
    <LayerCanvas document={document} onChange={(value) => change(value.layers)} />
    <ol className="grid gap-2" aria-label="Certificate layers">{document.layers.map((layer, index) => <li key={layer.id} className="flex flex-wrap items-center gap-2 rounded-control border border-line p-2">
      <button type="button" className="desk-button flex-1" aria-pressed={current?.id === layer.id} onClick={() => setSelected(layer.id)}>{index + 1}. {layer.type === "text" ? layer.text || "Text" : layer.type.replace(/_/g, " ")}</button>
      <button className="desk-button min-h-11" type="button" aria-label={`Move layer ${index + 1} up`} disabled={index === 0} onClick={() => change(reorder(document.layers, index, index-1))}><ArrowUp size={16} aria-hidden="true" /></button>
      <button className="desk-button min-h-11" type="button" aria-label={`Move layer ${index + 1} down`} disabled={index === document.layers.length-1} onClick={() => change(reorder(document.layers, index, index+1))}><ArrowDown size={16} aria-hidden="true" /></button>
      <button className="desk-button min-h-11" type="button" aria-label={`Duplicate layer ${index + 1}`} disabled={document.layers.length >= 20} onClick={() => change(duplicate(document.layers, layer.id))}><Copy size={16} aria-hidden="true" /></button>
      <button className="desk-button min-h-11" type="button" aria-label={`Delete layer ${index + 1}`} disabled={document.layers.length === 1} onClick={() => change(document.layers.filter((row) => row.id !== layer.id).map((row, order) => ({ ...row, order })))}><Trash2 size={16} aria-hidden="true" /></button>
    </li>)}</ol>
    <PositionedLayoutEditor widthMm={document.page_width_mm} heightMm={document.page_height_mm} gridMm={grid}
      onGridChange={setGrid} elements={positioned} labels={Object.fromEntries(document.layers.map((row) => [row.id, row.text || row.type]))}
      onChange={(elements) => change(document.layers.map((layer) => {
        const next = elements.find((row) => row.field === layer.id)!;
        return { ...layer, x_mm: next.x_mm, y_mm: next.y_mm, width_mm: next.width_mm, height_mm: next.height_mm,
          ...(layer.type === "text" ? { font_size_pt: next.font_size_pt, align: next.align } : {}) };
      }))} />
    {current ? <LayerInspector layer={current} onChange={patch} /> : null}
  </fieldset>;
}

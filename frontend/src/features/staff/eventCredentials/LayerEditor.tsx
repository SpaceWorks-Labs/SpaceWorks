import { useCallback, useState } from "react";
import { Plus, Redo2, Undo2 } from "lucide-react";
import { SegmentedControl } from "../../../components/ui/SegmentedControl";
import { useUndoHistory, useUndoShortcuts } from "../../../components/card-designer/undoHistory";
import { duplicate, newTextLayer, reorder, type Layer, type LayerDocument } from "./layout";
import { badgeSampleValues } from "./badgeStocks";
import { LayerInspector } from "./LayerInspector";
import { DesignCanvas, type Zoom } from "./designer/DesignCanvas";
import { LayerList } from "./designer/LayerList";
import { alignToPage, hasNameTag, keepOnPage, measurablePaper } from "./designer/geometry";

const SLOTS: Partial<Record<Layer["type"], string>> = { logo: "logo", certificate_qr: "certificate_verification_qr",
  event_credential_qr: "event_credential_qr", photo: "selected_member_photo" };
const ZOOMS: { value: string; label: string }[] = [{ value: "fit", label: "Fit" }, { value: "1", label: "100%" },
  { value: "1.5", label: "150%" }, { value: "2", label: "200%" }];

/** The certificate and event badge layer editor. Shares the card designer's undo/redo (50 snapshots,
 *  Ctrl/Cmd+Z, Shift+Ctrl/Cmd+Z); a drag, resize or rotate is one undo step. */
export function LayerEditor({ document, onChange, disabled = false, kind = "certificate", values, signatures }: {
  document: LayerDocument; onChange: (value: LayerDocument) => void; disabled?: boolean; kind?: "certificate" | "badge";
  values?: Record<string, string>; signatures?: Record<number, { name: string; title: string }>;
}) {
  const [selected, setSelected] = useState(document.layers[0]?.id);
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [longNames, setLongNames] = useState(false);
  const apply = useCallback((value: LayerDocument) => onChange(value), [onChange]);
  const history = useUndoHistory(document, apply);
  useUndoShortcuts(history.undo, history.redo, !disabled);
  const current = document.layers.find((layer) => layer.id === selected) ?? document.layers[0];
  const page = { width: document.page_width_mm, height: document.page_height_mm };
  const live = (layers: Layer[]) => onChange({ ...document, layers });
  function change(layers: Layer[]) { history.record(document); live(layers); }
  function patch(value: Partial<Layer>) {
    if (!current) return;
    const next = { ...current, ...value };
    const geometric = ["x_mm", "y_mm", "width_mm", "height_mm"].some((key) => key in value);
    change(document.layers.map((row) => row.id === current.id ? (geometric ? { ...next, ...keepOnPage(next, page) } : next) : row));
  }
  function remove(id: string) {
    const layers = document.layers.filter((row) => row.id !== id).map((row, order) => ({ ...row, order }));
    if (!layers.length) return;
    change(layers); setSelected(layers[Math.max(0, layers.findIndex((row) => row.order === 0))]?.id);
  }
  function copy(id: string) {
    const next = duplicate(document.layers, id);
    if (next !== document.layers) { change(next); setSelected(next[next.length - 1].id); }
  }
  function add(type: Layer["type"]) {
    const base = newTextLayer(document.layers.length);
    const size = type === "signature" ? { width_mm: 60, height_mm: 30 } : type.endsWith("qr") ? { width_mm: 25, height_mm: 25 } : { width_mm: 25, height_mm: 25 };
    const next: Layer = type === "text" ? base : { id: base.id, order: base.order, type, x_mm: 10, y_mm: 10, rotation: 0, ...size,
      ...(SLOTS[type] ? { resource_slot: SLOTS[type] } : {}),
      ...(type === "signature" ? { signature_slot: 1 as const, font_family: "Gilroy" as const, font_weight: 600 as const, font_size_pt: 11, align: "center" as const, colour_token: "ink" } : {}),
      ...(type === "certificate_id" ? { font_family: "Gilroy" as const, font_weight: 400 as const, font_size_pt: 7, align: "right" as const, colour_token: "ink", width_mm: 70, height_mm: 6 } : {}) };
    change([...document.layers, next]); setSelected(next.id);
  }
  const addTypes: Layer["type"][] = kind === "badge" ? ["text", "logo", "photo", "event_credential_qr"]
    : ["text", "logo", "signature", "certificate_qr", "certificate_id"];
  const canvasValues = values ?? (kind === "badge" ? badgeSampleValues(longNames) : undefined);
  return <fieldset className="grid min-w-0 gap-4" disabled={disabled}>
    <legend className="font-semibold text-ink">Layers ({document.layers.length}/20)</legend>
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button" disabled={!history.canUndo} onClick={history.undo} aria-keyshortcuts="Control+Z Meta+Z">
        <Undo2 size={16} aria-hidden="true" />Undo</button>
      <button type="button" className="desk-button" disabled={!history.canRedo} onClick={history.redo} aria-keyshortcuts="Control+Shift+Z Meta+Shift+Z">
        <Redo2 size={16} aria-hidden="true" />Redo</button>
      {addTypes.map((type) => <button className="desk-button" key={type} type="button" disabled={document.layers.length >= 20} onClick={() => add(type)}>
        <Plus size={16} aria-hidden="true" />Add {type === "certificate_qr" ? "verification QR" : type === "certificate_id" ? "certificate ID" : type.replace(/_/g, " ")}</button>)}
      {kind === "badge" ? <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
        <input type="checkbox" className="h-5 w-5" checked={longNames} onChange={(event) => setLongNames(event.target.checked)} />
        Preview a long name</label> : null}
    </div>
    {!hasNameTag(document) ? <p role="status" className="rounded-control border border-warn bg-warn-soft p-3 text-sm text-warn-ink">
      No visible layer prints {"{{name}}"}, so every copy would look the same. Add the recipient's name.</p> : null}
    <div className="flex flex-wrap items-center justify-between gap-2">
      <SegmentedControl label="Zoom" value={String(zoom)} options={ZOOMS} onChange={(value) => setZoom(value === "fit" ? "fit" : Number(value) as Zoom)} />
      <p className="text-xs text-muted">Drag to move (snaps to the centre and other layers; hold Alt to place freely). Corners resize (Shift stretches pictures). The top handle rotates (Shift: 15° steps).</p>
    </div>
    <DesignCanvas document={document} selectedId={current?.id} zoom={zoom} values={canvasValues} signatures={signatures}
      onSelect={setSelected} onBegin={() => history.record(document)} onLive={live} onChange={live}
      onDelete={remove} onDuplicate={copy} />
    <p className="text-xs text-muted">The canvas is a close guide. The PDF preview uses the final fonts, wrapping and pictures.</p>
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <LayerList layers={document.layers} selectedId={current?.id} onSelect={setSelected}
        onMove={(from, to) => change(reorder(document.layers, from, to))}
        onToggle={(id, key) => change(document.layers.map((row) => row.id === id ? { ...row, [key]: !row[key] } : row))}
        onDuplicate={copy} onDelete={remove} />
      {current ? <LayerInspector layer={current} onChange={patch} kind={kind} paperMeasurable={measurablePaper(document)}
        onAlign={(how) => patch(alignToPage(current, page, how))} /> : null}
    </div>
  </fieldset>;
}

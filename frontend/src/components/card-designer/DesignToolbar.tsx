// Undo/redo, side, stock, preview options, templates, the design file and the test print.
import { useState } from "react";
import { Download, Printer, Redo2, Undo2, Upload } from "lucide-react";

import { ConfirmDialog } from "../ui/ConfirmDialog";
import type { CardDesign, CardDocument, SideName } from "./cardTypes";
import { GRID_SIZES_MM, STOCKS } from "./cardGeometry";
import { exportDesign, importDesign, previewBlob, useResetDesign, useTemplates } from "./designerApi";
import { NumberInput, SelectInput, Toggle } from "./inspectorFields";

export type ViewOptions = { side: SideName; longNames: boolean; showGrid: boolean; gridMm: number };

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(window.document.createElement("a"), { href: url, download: name });
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function DesignToolbar({ design, document, view, onView, onDocument, onStock, onAdopt, history, canEdit, flush }: {
  design: CardDesign; document: CardDocument; view: ViewOptions; onView: (view: ViewOptions) => void;
  onDocument: (change: (current: CardDocument) => CardDocument) => void;
  onStock: (stock: string, width?: number, height?: number) => void; onAdopt: (design: CardDesign) => void;
  history: { undo: () => void; redo: () => void; canUndo: boolean; canRedo: boolean }; canEdit: boolean;
  flush: () => Promise<void>;
}) {
  const templates = useTemplates(design.id);
  const reset = useResetDesign(design.id);
  const [template, setTemplate] = useState<string | null>(null);
  const [message, setMessage] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [printing, setPrinting] = useState(false);
  const fail = (error: unknown, fallback: string) => setMessage({ tone: "error", text: error instanceof Error ? error.message : fallback });

  async function testPrint() {
    setPrinting(true); setMessage(null);
    try {
      save(await previewBlob(design.id, document, view.side, "pdf", view.longNames), `card-design-${design.id}-test.pdf`);
      setMessage({ tone: "info", text: "Print the PDF at 100 % (actual size) and check it against a real card." });
    } catch (error) { fail(error, "The test print couldn't be made."); } finally { setPrinting(false); }
  }

  async function exportFile() {
    try {
      await flush();
      const file = await exportDesign(design.id);
      save(new Blob([JSON.stringify(file, null, 2)], { type: "application/json" }), `card-design-${design.id}.json`);
    } catch (error) { fail(error, "The design file couldn't be downloaded."); }
  }

  async function importFile(file: File) {
    try {
      const parsed: unknown = JSON.parse(await file.text());
      await flush();
      const result = await importDesign(design.id, parsed);
      onAdopt(result.design);
      setMessage({ tone: "info", text: result.notes.length ? result.notes.join(" ") : "Design imported." });
    } catch (error) { fail(error, "That file isn't a card design."); }
  }

  const custom = document.stock === "custom";
  return <div className="grid gap-3">
    <div className="flex flex-wrap items-end gap-2">
      <button type="button" className="desk-button-ghost min-h-11" aria-label="Undo" disabled={!canEdit || !history.canUndo}
        onClick={history.undo}><Undo2 size={16} aria-hidden="true" /></button>
      <button type="button" className="desk-button-ghost min-h-11" aria-label="Redo" disabled={!canEdit || !history.canRedo}
        onClick={history.redo}><Redo2 size={16} aria-hidden="true" /></button>
      <div role="radiogroup" aria-label="Side" className="inline-flex gap-1 rounded-control border border-line bg-surface p-1">
        {(["front", "back"] as const).map((side) => <button key={side} type="button" role="radio" aria-checked={view.side === side}
          disabled={side === "back" && !document.back_enabled}
          className={`min-h-11 rounded-control px-4 text-sm font-semibold ${view.side === side ? "bg-panel text-ink" : "text-muted"} disabled:opacity-40`}
          onClick={() => onView({ ...view, side })}>{side === "front" ? "Front" : "Back"}</button>)}
      </div>
      <Toggle label="Two-sided" checked={document.back_enabled} disabled={!canEdit} onChange={(back_enabled) => {
        onDocument((current) => ({ ...current, back_enabled }));
        if (!back_enabled) onView({ ...view, side: "front" });
      }} />
      <Toggle label="Long sample names" checked={view.longNames} onChange={(longNames) => onView({ ...view, longNames })} />
      <Toggle label="Black and white" checked={document.mono} disabled={!canEdit}
        onChange={(mono) => onDocument((current) => ({ ...current, mono }))} />
      <Toggle label="Grid" checked={view.showGrid} onChange={(showGrid) => onView({ ...view, showGrid })} />
      <SelectInput label="Snap" value={String(view.gridMm)} onChange={(value) => onView({ ...view, gridMm: Number(value) })}
        options={GRID_SIZES_MM.map((size) => ({ value: String(size), label: `${size} mm` }))} />
    </div>
    <div className="flex flex-wrap items-end gap-2">
      <SelectInput label="Card size" value={document.stock} disabled={!canEdit} onChange={(stock) => onStock(stock)}
        options={STOCKS.map((stock) => ({ value: stock.key, label: stock.label }))} />
      {custom ? <>
        <NumberInput label="Width" unit="mm" value={document.page_width_mm ?? document.front.page_width_mm} min={40} max={300}
          disabled={!canEdit} onChange={(width) => onStock("custom", width, document.front.page_height_mm)} />
        <NumberInput label="Height" unit="mm" value={document.page_height_mm ?? document.front.page_height_mm} min={40} max={300}
          disabled={!canEdit} onChange={(height) => onStock("custom", document.front.page_width_mm, height)} />
      </> : null}
      {canEdit ? <SelectInput label="Start from a template" value="" onChange={(key) => key && setTemplate(key)}
        options={[{ value: "", label: "Choose…" }, ...(templates.data ?? []).map((item) => ({ value: item.key, label: item.label }))]} /> : null}
      <button type="button" className="desk-button min-h-11" disabled={printing} onClick={() => void testPrint()}>
        <Printer size={16} aria-hidden="true" /> {printing ? "Making the PDF…" : "Test print"}</button>
      {canEdit ? <>
        <button type="button" className="desk-button-ghost min-h-11" onClick={() => void exportFile()}>
          <Download size={16} aria-hidden="true" /> Design file</button>
        <label className="desk-button-ghost min-h-11 cursor-pointer"><Upload size={16} aria-hidden="true" /> Import
          <input type="file" accept="application/json,.json" className="sr-only" onChange={(event) => {
            const file = event.target.files?.[0]; event.target.value = ""; if (file) void importFile(file);
          }} /></label>
      </> : null}
    </div>
    {message ? <p role={message.tone === "error" ? "alert" : "status"}
      className={`text-sm ${message.tone === "error" ? "text-danger" : "text-muted"}`}>{message.text}</p> : null}
    <ConfirmDialog open={template !== null} title="Start again from this template?"
      message="Your draft is replaced. Cards keep the published version until you publish again." confirmLabel="Replace the draft"
      pending={reset.isPending} onCancel={() => setTemplate(null)}
      onConfirm={() => void reset.mutateAsync({ template }).then((saved) => { onAdopt(saved); setTemplate(null); })
        .catch((error) => { setTemplate(null); fail(error, "The template couldn't be applied."); })} />
  </div>;
}

// Undo/redo, side, stock and view options; then templates, "Preview as", the test print, the
// calibration sheet, the design file, checks and shortcuts. On phones the file tools fold into "More".
import { useRef, useState } from "react";
import { Download, Keyboard, ListChecks, Printer, Redo2, Undo2, Upload } from "lucide-react";

import { OverflowMenu } from "../ui/OverflowMenu";
import type { CardDesign, CardDocument, SideName } from "./cardTypes";
import { GRID_SIZES_MM, STOCKS } from "./cardGeometry";
import { exportDesign, importDesign } from "./designerApi";
import { calibrationSheet, exactPreview, saveBlob, type CalibrationPaper } from "./designerHistoryApi";
import { NumberInput, SelectInput, Toggle } from "./inspectorFields";
import { PreviewAsControl } from "./PreviewAsControl";
import type { PreviewPerson } from "./previewPerson";
import { TemplateGallery } from "./TemplateGallery";

export type ViewOptions = { side: SideName; showGrid: boolean; gridMm: number };
const PAPERS: { value: CalibrationPaper; label: string }[] = [
  { value: "a4", label: "A4 paper" }, { value: "letter", label: "Letter paper" }, { value: "card", label: "Single card (PVC printer)" },
];
const CALIBRATION_HINT = "Print at 100 %: each ruler should measure exactly 100 mm.";

export function DesignToolbar({ design, document, view, onView, onDocument, onStock, onAdopt, history, canEdit, flush,
  person, onPerson, values, checks, onShowChecks, onShortcuts }: {
  design: CardDesign; document: CardDocument; view: ViewOptions; onView: (view: ViewOptions) => void;
  onDocument: (change: (current: CardDocument) => CardDocument) => void;
  onStock: (stock: string, width?: number, height?: number) => void; onAdopt: (design: CardDesign) => void;
  history: { undo: () => void; redo: () => void; canUndo: boolean; canRedo: boolean }; canEdit: boolean;
  flush: () => Promise<void>; person: PreviewPerson; onPerson: (person: PreviewPerson) => void; values: Record<string, string>;
  checks: { count: number; errors: number }; onShowChecks: () => void; onShortcuts: () => void;
}) {
  const [message, setMessage] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const fail = (error: unknown, fallback: string) => setMessage({ tone: "error", text: error instanceof Error ? error.message : fallback });

  async function run(key: string, work: () => Promise<string>, fallback: string) {
    setBusy(key); setMessage(null);
    try { setMessage({ tone: "info", text: await work() }); } catch (error) { fail(error, fallback); } finally { setBusy(null); }
  }
  const testPrint = () => run("print", async () => {
    saveBlob(await exactPreview(design.id, document, view.side, { format: "pdf", longNames: person.kind === "long",
      holderId: person.kind === "holder" ? person.holder.id : null }), `card-design-${design.id}-test.pdf`);
    return "Print the PDF at 100 % (actual size) and check it against a real card.";
  }, "The test print couldn't be made.");
  const calibrate = (paper: CalibrationPaper) => run("calibrate", async () => {
    saveBlob(await calibrationSheet(design.id, paper), `card-calibration-${paper}.pdf`);
    return CALIBRATION_HINT;
  }, "The calibration sheet couldn't be made.");
  const exportFile = () => run("export", async () => {
    await flush();
    saveBlob(new Blob([JSON.stringify(await exportDesign(design.id), null, 2)], { type: "application/json" }), `card-design-${design.id}.json`);
    return "Design file downloaded.";
  }, "The design file couldn't be downloaded.");
  const importFile = (file: File) => run("import", async () => {
    let parsed: unknown;
    try { parsed = JSON.parse(await file.text()); } catch { throw new Error("That file isn't a card design."); }
    await flush();
    const result = await importDesign(design.id, parsed);
    onAdopt(result.design);
    return result.notes.length ? result.notes.join(" ") : "Design imported.";
  }, "That file isn't a card design.");

  const custom = document.stock === "custom";
  const calibration = PAPERS.map((paper) => ({ label: paper.label, onClick: () => void calibrate(paper.value) }));
  return <div className="grid gap-3">
    <div className="flex flex-wrap items-end gap-2">
      <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label="Undo" title="Undo (Ctrl or Cmd + Z)"
        disabled={!canEdit || !history.canUndo} onClick={history.undo}><Undo2 size={16} aria-hidden="true" /></button>
      <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label="Redo" title="Redo (Shift + Ctrl or Cmd + Z)"
        disabled={!canEdit || !history.canRedo} onClick={history.redo}><Redo2 size={16} aria-hidden="true" /></button>
      <div role="radiogroup" aria-label="Side" className="inline-flex gap-1 rounded-control border border-line bg-surface p-1">
        {(["front", "back"] as const).map((side) => <button key={side} type="button" role="radio" aria-checked={view.side === side}
          disabled={side === "back" && !document.back_enabled}
          className={`min-h-11 rounded-control px-4 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-focus ${view.side === side ? "bg-panel text-ink" : "text-muted"} disabled:opacity-40`}
          onClick={() => onView({ ...view, side })}>{side === "front" ? "Front" : "Back"}</button>)}
      </div>
      <Toggle label="Two-sided" checked={document.back_enabled} disabled={!canEdit} onChange={(back_enabled) => {
        onDocument((current) => ({ ...current, back_enabled }));
        if (!back_enabled) onView({ ...view, side: "front" });
      }} />
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
      {canEdit ? <TemplateGallery design={design} values={values} onAdopt={onAdopt}
        onError={(error) => fail(error, "The template couldn't be applied.")} /> : null}
      <PreviewAsControl design={design} document={document} person={person} onPerson={onPerson} />
    </div>
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button min-h-11" disabled={busy === "print"} onClick={() => void testPrint()}>
        <Printer size={16} aria-hidden="true" /> {busy === "print" ? "Making the PDF…" : "Test print"}</button>
      <OverflowMenu className="hidden sm:block" label="Calibration sheet" showLabel actions={calibration} />
      {canEdit ? <>
        <button type="button" className="desk-button-ghost hidden min-h-11 sm:inline-flex" onClick={() => void exportFile()}>
          <Download size={16} aria-hidden="true" /> Design file</button>
        <button type="button" className="desk-button-ghost hidden min-h-11 sm:inline-flex" onClick={() => fileInput.current?.click()}>
          <Upload size={16} aria-hidden="true" /> Import</button>
      </> : null}
      <input ref={fileInput} type="file" accept="application/json,.json" className="sr-only" tabIndex={-1} aria-hidden="true"
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void importFile(file); }} />
      <button type="button" className="desk-button min-h-11" onClick={onShowChecks}
        aria-label={checks.count ? `Checks: ${checks.count} to look at` : "Checks: all passed"}>
        <ListChecks size={16} aria-hidden="true" /> Checks
        <span aria-hidden="true" className={`min-w-6 rounded-full px-1.5 text-center text-xs font-bold tabular-nums ${checks.errors
          ? "bg-danger text-on-danger" : checks.count ? "bg-warn text-on-warn" : "bg-success text-on-success"}`}>{checks.count}</span>
      </button>
      <button type="button" className="desk-button-ghost hidden min-h-11 sm:inline-flex" onClick={onShortcuts}>
        <Keyboard size={16} aria-hidden="true" /> Keyboard shortcuts</button>
      <OverflowMenu className="sm:hidden" label="More tools" actions={[
        ...calibration.map((item) => ({ ...item, label: `Calibration sheet, ${item.label}` })),
        ...(canEdit ? [{ label: "Download the design file", onClick: () => void exportFile() },
          { label: "Import a design file", onClick: () => fileInput.current?.click() }] : []),
        { label: "Keyboard shortcuts", onClick: onShortcuts }]} />
    </div>
    {message ? <p role={message.tone === "error" ? "alert" : "status"}
      className={`text-sm ${message.tone === "error" ? "text-danger" : "text-muted"}`}>{message.text}</p> : null}
  </div>;
}

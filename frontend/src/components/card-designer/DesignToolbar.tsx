// The slim top bar's tools: undo/redo, zoom, "Preview as", the exact preview, the test print, and a File menu
// (print-ready PDF and PNG, cards from a CSV, design file, import, calibration sheets, checks, shortcuts). View
// options live in the canvas bar, card size in the Page tab, templates in the left rail.
import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";
import { Printer, Redo2, Undo2 } from "lucide-react";

import { OverflowMenu } from "../ui/OverflowMenu";
import { SegmentedControl } from "../ui/SegmentedControl";
import type { CardDesign, CardDocument, SideName } from "./cardTypes";
import { zoomPresets, type Zoom } from "./canvasMath";
import { exportDesign, importDesign } from "./designerApi";
import { CsvMergeDialog } from "./CsvMergeDialog";
import { calibrationSheet, exactPreview, saveBlob, type CalibrationPaper } from "./designerHistoryApi";
import { PreviewAsControl } from "./PreviewAsControl";
import { isLongPerson, type PreviewPerson } from "./previewPerson";

export type ViewOptions = { side: SideName; showGrid: boolean; gridMm: number; showRulers?: boolean };
const papers = (): { value: CalibrationPaper; label: string }[] => [
  { value: "a4", label: t`A4 paper` }, { value: "letter", label: t`Letter paper` }, { value: "card", label: t`Single card (PVC printer)` },
];
/** Print-ready exports use the design's bleed guide, or the common 3 mm when none is set. */
export const exportBleed = (document: CardDocument) => (document.guides?.bleed_mm && document.guides.bleed_mm > 0 ? document.guides.bleed_mm : 3);

export function DesignToolbar({ design, document, view, onAdopt, history, canEdit, flush, person, onPerson, zoom, onZoom,
  checks, onShowChecks, onShortcuts, messageSlot }: {
  design: CardDesign; document: CardDocument; view: ViewOptions; onAdopt: (design: CardDesign) => void;
  history: { undo: () => void; redo: () => void; canUndo: boolean; canRedo: boolean }; canEdit: boolean;
  flush: () => Promise<void>; person: PreviewPerson; onPerson: (person: PreviewPerson) => void;
  zoom: Zoom; onZoom: (zoom: Zoom) => void;
  checks: { count: number; errors: number }; onShowChecks: () => void; onShortcuts: () => void;
  /** Receives the last status message so the bar can show it under itself. */ messageSlot?: (message: { tone: "info" | "error"; text: string } | null) => void;
}) {
  const [message, setMessageState] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [csvOpen, setCsvOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const setMessage = (next: { tone: "info" | "error"; text: string } | null) => { setMessageState(next); messageSlot?.(next); };
  const fail = (error: unknown, fallback: string) => setMessage({ tone: "error", text: error instanceof Error ? error.message : fallback });

  async function run(key: string, work: () => Promise<string>, fallback: string) {
    setBusy(key); setMessage(null);
    try { setMessage({ tone: "info", text: await work() }); } catch (error) { fail(error, fallback); } finally { setBusy(null); }
  }
  const holderId = person.kind === "holder" ? person.holder.id : null;
  const testPrint = () => run("print", async () => {
    saveBlob(await exactPreview(design.id, document, view.side, { format: "pdf", longNames: isLongPerson(person), holderId }),
      `card-design-${design.id}-test.pdf`);
    return t`Print the PDF at 100 % (actual size) and check it against a real card.`;
  }, t`The test print couldn't be made.`);
  const printReady = (format: "pdf" | "png") => run("ready", async () => {
    const bleedMm = exportBleed(document);
    saveBlob(await exactPreview(design.id, document, view.side, { format, longNames: isLongPerson(person), holderId, bleedMm,
      cropMarks: format === "pdf", dpi: 300 }), `card-design-${design.id}-print.${format}`);
    return format === "pdf" ? t`Print-ready PDF with ${bleedMm} mm bleed and crop marks. Proofs carry the PREVIEW mark; real cards come from each card's download.`
      : t`300 dpi PNG with ${bleedMm} mm bleed, for online print services.`;
  }, t`The print-ready file couldn't be made.`);
  const calibrate = (paper: CalibrationPaper) => run("calibrate", async () => {
    saveBlob(await calibrationSheet(design.id, paper), `card-calibration-${paper}.pdf`);
    return t`Print at 100 %: each ruler should measure exactly 100 mm.`;
  }, t`The calibration sheet couldn't be made.`);
  const exportFile = () => run("export", async () => {
    await flush();
    saveBlob(new Blob([JSON.stringify(await exportDesign(design.id), null, 2)], { type: "application/json" }), `card-design-${design.id}.json`);
    return t`Design file downloaded.`;
  }, t`The design file couldn't be downloaded.`);
  const importFile = (file: File) => run("import", async () => {
    let parsed: unknown;
    try { parsed = JSON.parse(await file.text()); } catch { throw new Error(t`That file isn't a card design.`); }
    await flush();
    const result = await importDesign(design.id, parsed);
    onAdopt(result.design);
    return result.notes.length ? result.notes.join(" ") : t`Design imported.`;
  }, t`That file isn't a card design.`);

  const menu = [
    { label: t`Print-ready PDF (bleed and crop marks)`, onClick: () => void printReady("pdf") },
    { label: t`Print-ready PNG (300 dpi, bleed)`, onClick: () => void printReady("png") },
    ...(canEdit ? [{ label: t`Cards from a CSV file…`, onClick: () => setCsvOpen(true) },
      { label: t`Download the design file`, onClick: () => void exportFile() },
      { label: t`Import a design file`, onClick: () => fileInput.current?.click() }] : []),
    ...papers().map((paper) => ({ label: t`Calibration sheet, ${paper.label}`, onClick: () => void calibrate(paper.value) })),
    { label: checks.count ? t`Checks (${checks.count} to look at)` : t`Checks (all passed)`, onClick: onShowChecks },
    { label: t`Keyboard shortcuts`, onClick: onShortcuts },
  ];
  return <div className="flex flex-wrap items-center gap-2">
    <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={t`Undo`} title={t`Undo (Ctrl or Cmd + Z)`}
      disabled={!canEdit || !history.canUndo} onClick={history.undo}><Undo2 size={16} aria-hidden="true" /></button>
    <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={t`Redo`} title={t`Redo (Shift + Ctrl or Cmd + Z)`}
      disabled={!canEdit || !history.canRedo} onClick={history.redo}><Redo2 size={16} aria-hidden="true" /></button>
    <SegmentedControl label={t`Zoom`} value={String(zoom)} onChange={(value) => onZoom(value === "fit" ? "fit" : Number(value))}
      options={zoomPresets().map((item) => ({ value: String(item.value), label: item.label }))} />
    <PreviewAsControl design={design} document={document} person={person} onPerson={onPerson} />
    <button type="button" className="desk-button min-h-11" disabled={busy === "print"} onClick={() => void testPrint()}>
      <Printer size={16} aria-hidden="true" /> {busy === "print" ? t`Making the PDF…` : t`Test print`}</button>
    <OverflowMenu label={t`File`} showLabel actions={menu} />
    <input ref={fileInput} type="file" accept="application/json,.json" className="sr-only" tabIndex={-1} aria-hidden="true"
      onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void importFile(file); }} />
    {csvOpen ? <CsvMergeDialog design={design} open onClose={() => setCsvOpen(false)} /> : null}
    {message && !messageSlot ? <p role={message.tone === "error" ? "alert" : "status"}
      className={`basis-full text-sm ${message.tone === "error" ? "text-danger" : "text-muted"}`}>{message.text}</p> : null}
  </div>;
}

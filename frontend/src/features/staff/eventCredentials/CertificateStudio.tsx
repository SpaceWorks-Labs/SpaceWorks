// The certificate designer: the same studio as member and event cards (left rail, canvas, inspector), with a
// certificate preset: A4/Letter/A5 paper, signature rows bound to the event's signatories, a seal, the serial and the
// verification QR. Edits a v3 document held by the caller; saving, the PDF preview, approval, publication and bulk
// issue stay with the surrounding screen. The built-in looks come from the server.
import { t } from "@lingui/core/macro";
import { Redo2, Undo2 } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";

import { SegmentedControl } from "../../../components/ui/SegmentedControl";
import type { CardDocument, StudioSubject } from "../../../components/card-designer/cardTypes";
import { stepZoom, zoomPresets, type Zoom } from "../../../components/card-designer/canvasMath";
import { CanvasToolbar } from "../../../components/card-designer/CanvasToolbar";
import { CardCanvas } from "../../../components/card-designer/CardCanvas";
import { DesignerSidePanel, type Panel } from "../../../components/card-designer/DesignerSidePanel";
import { addRulerLine, layerName } from "../../../components/card-designer/designDocument";
import { LayerInspector } from "../../../components/card-designer/LayerInspector";
import { SelectInput } from "../../../components/card-designer/inspectorFields";
import type { PickModifiers } from "../../../components/card-designer/LayerList";
import { issueCount, preflight } from "../../../components/card-designer/preflight";
import { clickSelection, pruneSelection } from "../../../components/card-designer/selection";
import { CanvasBar, StudioRail } from "../../../components/card-designer/StudioChrome";
import { StudioAssetsProvider, type StudioAssets } from "../../../components/card-designer/studioAssets";
import { ShortcutsDialog } from "../../../components/card-designer/ShortcutsDialog";
import { useUndoHistory } from "../../../components/card-designer/undoHistory";
import { useDesignerKeys } from "../../../components/card-designer/useDesignerKeys";
import { useCardFonts } from "../../../components/card-designer/useCardFonts";
import { useDesignerEditing } from "../../../components/card-designer/useDesignerEditing";
import type { ViewOptions } from "../../../components/card-designer/DesignToolbar";
import { CERTIFICATE_FIELDS } from "./certificateLayout";
import { fetchLook, useCertificateLooks } from "./certificateLooks";

const SUBJECT: StudioSubject = { id: 0, domain: "certificate", answer_fields: [] };
const box = "min-h-0 min-w-0 overflow-y-auto overscroll-contain rounded-card border border-line bg-panel p-3 [&_.grid>*]:min-w-0 [&_input]:min-w-0";

export function CertificateStudio({ document, onChange, disabled = false, values, assets, makerspaceId }: {
  document: CardDocument; onChange: (document: CardDocument) => void; disabled?: boolean;
  values: Record<string, string>; assets: StudioAssets; makerspaceId?: number;
}) {
  const latest = useRef(document);
  latest.current = document;
  const apply = useCallback((next: CardDocument) => { latest.current = next; onChange(next); }, [onChange]);
  const history = useUndoHistory(document, apply);
  const scope = useRef<HTMLElement>(null);
  const [shortcuts, setShortcuts] = useState(false);
  const [selection, setRaw] = useState<string[]>([]);
  const [panel, setPanel] = useState<Panel>("add");
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [view, setView] = useState<ViewOptions>({ side: "front", showGrid: false, gridMm: 1, showRulers: true });
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [lookError, setLookError] = useState<string | null>(null);
  const [assetColours, setAssetColours] = useState<Record<string, string>>({});
  const looks = useCertificateLooks(makerspaceId);
  const side = document.front;
  const chosen = pruneSelection(side, selection);
  const update = useCallback((change: (current: CardDocument) => CardDocument, record = true) => {
    if (disabled) return;
    const previous = latest.current;
    const next = change(previous);
    if (next === previous) return;
    if (record) history.record(previous);
    apply(next);
  }, [disabled, history, apply]);
  const editing = useDesignerEditing({ update, sideName: "front", side, stock: document.stock, selection: chosen, setSelection: setRaw,
    canEdit: !disabled, safeMm: document.guides?.safe_mm });
  // The same keyboard as the card studio: undo/redo, copy/paste, group, arrange, nudge, zoom (decision 344(c)).
  useDesignerKeys(scope, { editing, selection: chosen, undo: history.undo, redo: history.redo, help: () => setShortcuts(true),
    zoom: (to) => setZoom((current) => stepZoom(current, to)) });
  useCardFonts(0, useMemo(() => [document], [document]));
  const issues = useMemo(() => preflight(document, "event_card", assetColours).filter((issue) => issue.id !== "no-name"), [document, assetColours]);
  const primary = chosen.length === 1 ? side.layers.find((layer) => layer.id === chosen[0]) ?? null : null;
  const pick = (id: string, modifiers: PickModifiers) => setRaw(clickSelection(side.layers, modifiers.additive ? chosen : [], id, modifiers));

  async function chooseLook(key: string) {
    if (!key || makerspaceId === undefined) return;
    const name = looks.data?.find((item) => item.key === key)?.label ?? key;
    if (side.layers.length && !window.confirm(t`Replace this design with the ${name} look? You can undo it.`)) return;
    try {
      const next = await fetchLook(makerspaceId, key, theme);
      update(() => next);
      setRaw([]);
      setLookError(null);
    } catch (error) { setLookError(error instanceof Error ? error.message : t`That look couldn't be loaded.`); }
  }

  return <StudioAssetsProvider value={assets}>
    <section ref={scope} className="grid min-w-0 gap-3" aria-label={t`Certificate studio`}>
      <p role="note" className="rounded-control border border-warn bg-warn-soft p-3 text-sm text-warn-ink lg:hidden">
        {t`The certificate studio works best on a larger screen. You can still use it here, one panel at a time.`}</p>
      <header className="flex flex-wrap items-center gap-2 rounded-card border border-line bg-panel px-3 py-2">
        <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={t`Undo`} disabled={disabled || !history.canUndo} onClick={history.undo}>
          <Undo2 size={16} aria-hidden="true" /></button>
        <button type="button" className="desk-button-ghost min-h-11 min-w-11" aria-label={t`Redo`} disabled={disabled || !history.canRedo} onClick={history.redo}>
          <Redo2 size={16} aria-hidden="true" /></button>
        <SegmentedControl label={t`Zoom`} value={String(zoom)} onChange={(value) => setZoom(value === "fit" ? "fit" : Number(value))}
          options={zoomPresets().map((item) => ({ value: String(item.value), label: item.label }))} />
        {looks.data?.length ? <>
          <SegmentedControl label={t`Look colours`} value={theme} onChange={(value) => setTheme(value as "light" | "dark")}
            options={[{ value: "light", label: t`Light` }, { value: "dark", label: t`Dark` }]} />
          <SelectInput label={t`Start from a look`} value="" disabled={disabled}
            options={[{ value: "", label: t`Choose a look…` }, ...looks.data.map((item) => ({ value: item.key, label: item.label }))]}
            onChange={(key) => void chooseLook(key)} />
        </> : null}
        <button type="button" className="desk-button-ghost min-h-11" onClick={() => setShortcuts(true)}>{t`Keyboard shortcuts`}</button>
        <span className="ml-auto text-sm text-muted" role="status">{issueCount(issues) ? t`${issueCount(issues)} check(s) to look at` : t`All checks passed`}</span>
        {lookError ? <p role="alert" className="basis-full text-sm text-danger">{lookError}</p> : null}
      </header>
      <div className="grid grid-cols-1 gap-3 lg:h-[calc(100vh-12rem)] lg:min-h-[36rem] lg:grid-cols-[4rem_16.5rem_minmax(0,1fr)_20rem]">
        <StudioRail panel={panel} onPanel={setPanel} onTemplates={() => setPanel("add")} noHistory
          flagged={issues.filter((issue) => issue.severity !== "info").length} />
        <div className={box}>
          <DesignerSidePanel panel={panel} design={SUBJECT} document={document} sideName="front" selection={chosen}
            editing={editing} onPick={pick} onAssetColour={(id, colour) => setAssetColours((current) => ({ ...current, [id]: colour }))}
            update={update} issues={issues} onIssue={(_side, id) => setRaw(id ? [id] : [])} values={values} fieldOptions={CERTIFICATE_FIELDS()} />
        </div>
        <div className="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] gap-2">
          <div className="grid gap-1 rounded-card border border-line bg-panel px-3 py-1">
            <CanvasBar document={document} view={view} onView={setView} canEdit={!disabled} onDocument={(change) => update(change)} />
            <CanvasToolbar side={side} selection={chosen} editing={editing} />
          </div>
          <div className="min-h-0 overflow-auto rounded-card border border-line bg-surface p-4">
            <div className="mx-auto grid min-h-full w-full max-w-[64rem] content-center">
              <CardCanvas side={side} designId={0} values={values} mono={document.mono} stock={document.stock} watermark={document.watermark}
                selection={chosen} gridMm={view.gridMm} showGrid={view.showGrid} zoom={zoom} readOnly={disabled} guides={document.guides} sideName="front" onZoom={setZoom}
                showRulers={Boolean(view.showRulers)} onAddGuide={(axis, at_mm) => update((current) => addRulerLine(current, axis, at_mm))}
                onSelect={setRaw} onPatch={editing.patch} onCheckpoint={() => history.record(latest.current)}
                label={t`Certificate page, ${side.page_width_mm} by ${side.page_height_mm} mm`} />
            </div>
          </div>
        </div>
        <aside className={box} aria-label={t`Layer settings`}>
          {primary ? <>
            <h3 className="mb-1 truncate text-sm font-bold text-ink">{layerName(primary)}</h3>
            <LayerInspector side={side} layer={primary} designId={0} stock={document.stock} assetColours={assetColours} fieldOptions={CERTIFICATE_FIELDS()}
              readOnly={disabled} onChange={(change) => editing.patchOne(primary.id, change)} />
          </> : <p className="text-sm text-muted">{t`Select a layer on the page or in the Layers list to change it.`}</p>}
        </aside>
      </div>
      <ShortcutsDialog open={shortcuts} onClose={() => setShortcuts(false)} />
    </section>
  </StudioAssetsProvider>;
}

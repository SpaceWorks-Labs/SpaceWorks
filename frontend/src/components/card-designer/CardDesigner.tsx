// The free card designer: one design (member cards, an ID programme, event cards or tickets).
// Edits are drafts saved as you go; publishing (or approval) decides what cards print.
import { useMemo, useRef, useState } from "react";

import { ErrorBlock } from "../ui/ErrorBlock";
import { Skeleton } from "../ui/Skeleton";
import type { CardDesign, SideName } from "./cardTypes";
import { CardCanvas } from "./CardCanvas";
import { CanvasToolbar } from "./CanvasToolbar";
import type { Zoom } from "./canvasMath";
import { DesignActions } from "./DesignActions";
import { applyStock, layerName } from "./designDocument";
import { DesignerSidePanel, type Panel } from "./DesignerSidePanel";
import { DesignToolbar, type ViewOptions } from "./DesignToolbar";
import { useCardDesignQuery } from "./designerApi";
import { LayerInspector } from "./LayerInspector";
import type { PickModifiers } from "./LayerList";
import { issueCount, preflight } from "./preflight";
import { previewLabel, previewValues, type PreviewPerson } from "./previewPerson";
import { clickSelection, pruneSelection } from "./selection";
import { SelectionInspector } from "./SelectionInspector";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { useCardDesign } from "./useCardDesign";
import { useCardFonts } from "./useCardFonts";
import { useDesignerEditing } from "./useDesignerEditing";
import { useDesignerKeys } from "./useDesignerKeys";

export function CardDesigner({ designId, canEdit, title }: { designId: number; canEdit: boolean; title?: string }) {
  const query = useCardDesignQuery(designId);
  if (query.isLoading) return <Skeleton className="h-96 w-full" />;
  if (query.isError || !query.data) return <ErrorBlock error={query.error} resource="card design" onRetry={() => void query.refetch()} />;
  return <DesignerBody design={query.data} canEdit={canEdit} title={title} />;
}

function DesignerBody({ design, canEdit, title }: { design: CardDesign; canEdit: boolean; title?: string }) {
  const working = useCardDesign(design, canEdit);
  const { document, update } = working;
  const scope = useRef<HTMLElement>(null);
  const [view, setView] = useState<ViewOptions>({ side: "front", showGrid: false, gridMm: 1 });
  const [person, setPerson] = useState<PreviewPerson>({ kind: "short" });
  const [rawSelection, setSelection] = useState<string[]>([]);
  const [panel, setPanel] = useState<Panel>("add");
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [shortcuts, setShortcuts] = useState(false);
  const [assetColours, setAssetColours] = useState<Record<string, string>>({});
  const side = document[view.side];
  const selection = pruneSelection(side, rawSelection);
  const values = previewValues(person);
  const issues = useMemo(() => preflight(document, design.domain, assetColours), [document, design.domain, assetColours]);
  useCardFonts(design.id, useMemo(() => [document], [document]));
  const editing = useDesignerEditing({ update, sideName: view.side, side, stock: document.stock, selection, setSelection, canEdit });
  useDesignerKeys(scope, { editing, selection, undo: working.undo, redo: working.redo, help: () => setShortcuts(true) });
  const rememberColour = (assetId: string, colour: string) => setAssetColours((current) => ({ ...current, [assetId]: colour }));
  const changeView = (next: ViewOptions) => { if (next.side !== view.side) setSelection([]); setView(next); };
  const adopt = (fresh: CardDesign) => { working.adopt(fresh); setSelection([]); };
  const primary = selection.length === 1 ? side.layers.find((layer) => layer.id === selection[0]) ?? null : null;
  const pick = (id: string, modifiers: PickModifiers) =>
    setSelection(clickSelection(side.layers, modifiers.additive ? selection : [], id, modifiers));
  const showIssue = (sideName: SideName, layerId: string | null) => {
    if (sideName !== view.side) setView({ ...view, side: sideName });
    setSelection(layerId ? [layerId] : []);
  };

  return <section ref={scope} className="grid min-w-0 grid-cols-1 gap-4" aria-label={title ?? "Card designer"}>
    {working.deviceDraft ? <div role="status" className="flex flex-wrap items-center gap-2 rounded-control border border-warn bg-warn-soft p-3 text-sm text-warn-ink">
      <span className="min-w-0 flex-1">This device has changes that were not saved
        ({new Date(working.deviceDraft.savedAt).toLocaleString()}).</span>
      <button type="button" className="desk-button min-h-11" onClick={working.restoreDeviceDraft}>Restore them</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={working.discardDeviceDraft}>Discard</button>
    </div> : null}
    <DesignActions design={design} saveStatus={working.status} saveError={working.error} canEdit={canEdit}
      flush={working.flush} onRetry={() => void working.retry()} onReload={() => void working.reload()} />
    <DesignToolbar design={design} document={document} view={view} onView={changeView} canEdit={canEdit} flush={working.flush}
      onDocument={(change) => update(change)} onAdopt={adopt} person={person} onPerson={setPerson} values={values}
      onStock={(stock, width, height) => update((current) => applyStock(current, stock, width, height))}
      checks={{ count: issueCount(issues), errors: issues.filter((issue) => issue.severity === "error").length }}
      onShowChecks={() => setPanel("checks")} onShortcuts={() => setShortcuts(true)}
      history={{ undo: working.undo, redo: working.redo, canUndo: working.canUndo, canRedo: working.canRedo }} />
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[17rem_minmax(0,1fr)] xl:grid-cols-[17rem_minmax(0,1fr)_19rem]">
      <div className="grid min-w-0 grid-cols-1 content-start gap-3 lg:col-start-2 lg:row-start-1">
        <CanvasToolbar side={side} selection={selection} editing={editing} zoom={zoom} onZoom={setZoom} />
        <div className="mx-auto w-full max-w-[34rem]">
          <CardCanvas side={side} designId={design.id} values={values} mono={document.mono} stock={document.stock}
            watermark={document.watermark}
            selection={selection} gridMm={view.gridMm} showGrid={view.showGrid} zoom={zoom} readOnly={!canEdit}
            onSelect={setSelection} onPatch={editing.patch} onCheckpoint={working.checkpoint}
            label={`${view.side === "front" ? "Front" : "Back"} of the card, ${side.page_width_mm} by ${side.page_height_mm} mm`} />
        </div>
        <p className="text-center text-xs text-muted">The dashed line is the 3 mm safe area: keep text inside it.
          Showing {previewLabel(person)}.</p>
      </div>
      <aside className="self-start rounded-card border border-line bg-panel p-3 lg:col-start-2 lg:row-start-2 xl:col-start-3 xl:row-start-1" aria-label="Layer settings">
        {primary ? <>
          <h3 className="mb-3 text-sm font-semibold text-ink">{layerName(primary)}</h3>
          <LayerInspector side={side} layer={primary} designId={design.id} stock={document.stock} assetColours={assetColours}
            answerFields={design.answer_fields}
            readOnly={!canEdit} onChange={(change) => editing.patchOne(primary.id, change)} />
        </> : selection.length > 1 ? <SelectionInspector side={side} selection={selection} editing={editing} />
          : <p className="text-sm text-muted">Select a layer on the card or in the Layers list to change it. Shift-click to select several.</p>}
      </aside>
      <div className="lg:col-start-1 lg:row-span-2 lg:row-start-1 xl:row-span-1">
        <DesignerSidePanel panel={panel} onPanel={setPanel} design={design} document={document} sideName={view.side}
          selection={selection} editing={editing} onPick={pick} onAssetColour={rememberColour} update={update}
          issues={issues} onIssue={showIssue} values={values}
          history={{ prepare: async () => {
            if (working.status === "pending" || working.status === "saving") await working.flush();
            return working.currentRevision();
          }, onRestored: adopt, onReload: () => void working.reload() }} />
      </div>
    </div>
    <ShortcutsDialog open={shortcuts} onClose={() => setShortcuts(false)} />
  </section>;
}

// The free card designer: one design (member cards, an ID programme, event cards or tickets).
// Edits are drafts saved as you go; publishing (or approval) decides what cards print.
import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useMemo, useRef, useState } from "react";

import { ErrorBlock } from "../ui/ErrorBlock";
import type { CardDesign, SideName } from "./cardTypes";
import { CardCanvas } from "./CardCanvas";
import { CanvasToolbar } from "./CanvasToolbar";
import { stepZoom, type Zoom } from "./canvasMath";
import { DesignActions } from "./DesignActions";
import { addRulerLine, layerName } from "./designDocument";
import { DesignerSidePanel, type Panel } from "./DesignerSidePanel";
import { DesignToolbar, type ViewOptions } from "./DesignToolbar";
import { CanvasBar, StudioRail } from "./StudioChrome";
import { useCardDesignQuery } from "./designerApi";
import { useHolderCutout } from "./designerHistoryApi";
import { LayerInspector } from "./LayerInspector";
import type { PickModifiers } from "./LayerList";
import { holderPhotoState, SAMPLE_PHOTO } from "./photoVariant";
import { issueCount, preflight } from "./preflight";
import { previewLabel, previewValues, type PreviewPerson } from "./previewPerson";
import { clickSelection, pruneSelection } from "./selection";
import { SelectionInspector } from "./SelectionInspector";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { useCardDesign } from "./useCardDesign";
import { useCardFonts } from "./useCardFonts";
import { ModeSwitch, useStudioMode } from "./ModeSwitch";
import { QuickPanel } from "./QuickPanel";
import { StudioTemplates } from "./StudioTemplates";
import { useDesignerEditing } from "./useDesignerEditing";
import { useDesignerKeys } from "./useDesignerKeys";
import { LogoLoader } from "../LogoLoader";
import { useLayoutMedia } from "../layouts/useLayoutMedia";
import { BrandKitProvider } from "./brandKit";

export function CardDesigner({ designId, canEdit, title, makerspaceId, initialPerson }: { designId: number; canEdit: boolean; title?: string; makerspaceId?: number;
  /** Who the preview starts as (the owner's sample, a long name...); defaults to the short sample. */ initialPerson?: PreviewPerson }) {
  const query = useCardDesignQuery(designId);
  if (query.isLoading) return <LogoLoader size={48} className="min-h-96 py-3" />;
  if (query.isError || !query.data) return <ErrorBlock error={query.error} resource={t`card design`} onRetry={() => void query.refetch()} />;
  return <DesignerBody design={query.data} canEdit={canEdit} title={title} makerspaceId={makerspaceId ?? query.data.makerspace_id} initialPerson={initialPerson} />;
}

function DesignerBody({ design, canEdit, title, makerspaceId, initialPerson }: { design: CardDesign; canEdit: boolean; title?: string; makerspaceId?: number; initialPerson?: PreviewPerson }) {
  const working = useCardDesign(design, canEdit);
  const { document, update } = working;
  const scope = useRef<HTMLElement>(null);
  const [view, setView] = useState<ViewOptions>({ side: "front", showGrid: false, gridMm: 1, showRulers: true });
  const [person, setPerson] = useState<PreviewPerson>(initialPerson ?? { kind: "short" });
  const [rawSelection, setSelection] = useState<string[]>([]);
  const [panel, setPanel] = useState<Panel>("add");
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [shortcuts, setShortcuts] = useState(false);
  const [chosenMode, changeMode] = useStudioMode();
  // Phones get a preview with Quick edits only (colours, text, paper): no free-canvas dragging on a small touch screen.
  const phone = useLayoutMedia("(max-width: 639px)");
  const mode = phone ? "quick" : chosenMode;
  const [assetColours, setAssetColours] = useState<Record<string, string>>({});
  const side = document[view.side];
  const selection = pruneSelection(side, rawSelection);
  const values = previewValues(person);
  const holderCutout = useHolderCutout(person.kind === "holder" ? person.holder : null);
  const issues = useMemo(() => preflight(document, design.domain, assetColours), [document, design.domain, assetColours]);
  useCardFonts(design.id, useMemo(() => [document], [document]));
  const editing = useDesignerEditing({ update, sideName: view.side, side, stock: document.stock, selection, setSelection, canEdit,
    safeMm: document.guides?.safe_mm });
  useDesignerKeys(scope, { editing, selection, undo: working.undo, redo: working.redo, help: () => setShortcuts(true),
    zoom: (to) => setZoom((current) => stepZoom(current, to)) });
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

  const advanced = mode === "advanced";
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const templates = <StudioTemplates design={design} makerspaceId={makerspaceId} values={values} flush={working.flush}
    revision={working.currentRevision} kind={document.kind} onAdopt={adopt} onError={() => undefined}
    open={advanced ? templatesOpen : undefined} onClose={() => setTemplatesOpen(false)} />;
  const flagged = issues.filter((issue) => issue.severity !== "info").length;
  const panelBox = "min-h-0 min-w-0 overflow-y-auto overscroll-contain rounded-card border border-line bg-panel p-3 [&_.grid>*]:min-w-0 [&_input]:min-w-0";

  return <BrandKitProvider designId={design.id}><section ref={scope} className="grid min-w-0 grid-cols-1 gap-3" aria-label={title ?? t`Card designer`}>
    {working.deviceDraft ? <div role="status" className="flex flex-wrap items-center gap-2 rounded-control border border-warn bg-warn-soft p-3 text-sm text-warn-ink">
      <span className="min-w-0 flex-1">{t`This device has changes that were not saved (${new Date(working.deviceDraft.savedAt).toLocaleString(formatLocale())}).`}</span>
      <button type="button" className="desk-button min-h-11" onClick={working.restoreDeviceDraft}>{t`Restore them`}</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={working.discardDeviceDraft}>{t`Discard`}</button>
    </div> : null}
    <p role="note" className="rounded-control border border-warn bg-warn-soft p-3 text-sm text-warn-ink lg:hidden">
      {phone ? t`On a phone you see a preview and can make quick changes (colours, text, paper). Open the studio on a larger screen to move and edit layers.`
        : t`The card studio works best on a larger screen. You can still use it here, one panel at a time.`}</p>
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-card border border-line bg-panel px-3 py-2">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="max-w-[16rem] truncate text-base font-bold text-ink" title={design.name}>{design.name || title}</h2>
        <DesignActions design={design} saveStatus={working.status} saveError={working.error} canEdit={canEdit}
          flush={working.flush} onRetry={() => void working.retry()} onReload={() => void working.reload()} />
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        {phone ? null : <ModeSwitch mode={mode} onChange={changeMode} />}
        <DesignToolbar design={design} document={document} view={view} onAdopt={adopt} canEdit={canEdit} flush={working.flush}
          person={person} onPerson={setPerson} zoom={zoom} onZoom={setZoom}
          checks={{ count: issueCount(issues), errors: issues.filter((issue) => issue.severity === "error").length }}
          onShowChecks={() => { changeMode("advanced"); setPanel("checks"); }} onShortcuts={() => setShortcuts(true)}
          history={{ undo: working.undo, redo: working.redo, canUndo: working.canUndo, canRedo: working.canRedo }} />
      </div>
    </header>
    <div className={`grid grid-cols-1 gap-3 lg:h-[calc(100vh-10rem)] lg:min-h-[36rem] ${advanced ? "lg:grid-cols-[4rem_16.5rem_minmax(0,1fr)_20rem]" : "lg:grid-cols-[19rem_minmax(0,1fr)]"}`}>
      {advanced ? <StudioRail panel={panel} onPanel={setPanel} onTemplates={() => setTemplatesOpen(true)} flagged={flagged} /> : null}
      <div className={panelBox}>
        {advanced ? <DesignerSidePanel panel={panel} design={design} document={document} sideName={view.side}
          selection={selection} editing={editing} onPick={pick} onAssetColour={rememberColour} update={update}
          issues={issues} onIssue={showIssue} values={values}
          history={{ prepare: async () => {
            if (working.status === "pending" || working.status === "saving") await working.flush();
            return working.currentRevision();
          }, onRestored: adopt, onReload: () => void working.reload() }} />
          : <QuickPanel document={document} sideName={view.side} domain={design.domain} designId={design.id} editing={editing}
            update={update} onAssetColour={rememberColour} answerFields={design.answer_fields} templates={templates} />}
      </div>
      <div className={`grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] gap-2 lg:order-none ${phone ? "order-first" : ""}`}>
        <div className="grid gap-1 rounded-card border border-line bg-panel px-3 py-1">
          <CanvasBar document={document} view={view} onView={changeView} canEdit={canEdit} onDocument={(change) => update(change)} />
          {advanced ? <CanvasToolbar side={side} selection={selection} editing={editing} /> : null}
        </div>
        <div className="min-h-0 overflow-auto rounded-card border border-line bg-surface p-4">
          <div className="mx-auto grid min-h-full w-full max-w-[46rem] content-center gap-2">
            <CardCanvas side={side} designId={design.id} values={values} mono={document.mono} stock={document.stock}
              watermark={document.watermark} guides={document.guides} sideName={view.side} onZoom={setZoom}
              photoState={person.kind === "holder" ? holderPhotoState(holderCutout.data ?? null, person.holder.cutout) : SAMPLE_PHOTO}
              showRulers={Boolean(view.showRulers) && advanced} onAddGuide={(axis, at_mm) => update((current) => addRulerLine(current, axis, at_mm))}
              selection={selection} gridMm={view.gridMm} showGrid={view.showGrid} zoom={zoom} readOnly={!canEdit || phone}
              onSelect={setSelection} onPatch={editing.patch} onCheckpoint={working.checkpoint}
              label={view.side === "front" ? t`Front of the card, ${side.page_width_mm} by ${side.page_height_mm} mm` : t`Back of the card, ${side.page_width_mm} by ${side.page_height_mm} mm`} />
            <p className="text-center text-xs text-muted">{t`The dashed line is the safe area: keep text inside it. Showing ${previewLabel(person)}.`}</p>
          </div>
        </div>
      </div>
      {advanced ? <aside className={panelBox} aria-label={t`Layer settings`}>
        {primary ? <>
          <h3 className="mb-1 truncate text-sm font-bold text-ink">{layerName(primary)}</h3>
          <LayerInspector side={side} layer={primary} designId={design.id} stock={document.stock} assetColours={assetColours}
            answerFields={design.answer_fields}
            readOnly={!canEdit} onChange={(change) => editing.patchOne(primary.id, change)} />
        </> : selection.length > 1 ? <SelectionInspector side={side} selection={selection} editing={editing} />
          : <p className="text-sm text-muted">{t`Select a layer on the card or in the Layers list to change it. Shift-click to select several.`}</p>}
      </aside> : null}
    </div>
    <ShortcutsDialog open={shortcuts} onClose={() => setShortcuts(false)} />
    {!advanced ? null : templates}
  </section></BrandKitProvider>;
}

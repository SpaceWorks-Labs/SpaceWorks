// The free card designer: one design (member cards, an ID programme, event cards or tickets).
// Edits are drafts saved as you go; publishing (or approval) decides what cards print.
import { useEffect, useMemo, useState } from "react";

import { ErrorBlock } from "../ui/ErrorBlock";
import { SegmentedControl } from "../ui/SegmentedControl";
import { Skeleton } from "../ui/Skeleton";
import type { CardDesign, Layer } from "./cardTypes";
import { AddLayerMenu } from "./AddLayerMenu";
import { BackgroundPicker, WatermarkPicker } from "./BackgroundPicker";
import { CardCanvas } from "./CardCanvas";
import { SAMPLE_LONG, SAMPLE_SHORT } from "./dataFields";
import { DesignActions } from "./DesignActions";
import { addLayer, applyStock, duplicateLayer, layerName, moveLayer, patchLayer, removeLayer, withSide } from "./designDocument";
import { DesignToolbar, type ViewOptions } from "./DesignToolbar";
import { useCardDesignQuery } from "./designerApi";
import { loadCardFont } from "./fontLoader";
import { LayerInspector } from "./LayerInspector";
import { LayerList } from "./LayerList";
import { undoShortcut } from "./undoHistory";
import { useCardDesign } from "./useCardDesign";

export function CardDesigner({ designId, canEdit, title }: { designId: number; canEdit: boolean; title?: string }) {
  const query = useCardDesignQuery(designId);
  if (query.isLoading) return <Skeleton className="h-96 w-full" />;
  if (query.isError || !query.data) return <ErrorBlock error={query.error} resource="card design" onRetry={() => void query.refetch()} />;
  return <DesignerBody design={query.data} canEdit={canEdit} title={title} />;
}

type Panel = "add" | "layers" | "background";

function DesignerBody({ design, canEdit, title }: { design: CardDesign; canEdit: boolean; title?: string }) {
  const working = useCardDesign(design, canEdit);
  const { document, update } = working;
  const [view, setView] = useState<ViewOptions>({ side: "front", longNames: false, showGrid: false, gridMm: 1 });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>("add");
  const [assetColours, setAssetColours] = useState<Record<string, string>>({});
  const side = document[view.side];
  const selected = side.layers.find((layer) => layer.id === selectedId) ?? null;
  const values = view.longNames ? SAMPLE_LONG : SAMPLE_SHORT;
  const readOnly = !canEdit;
  const rememberColour = (assetId: string, colour: string) => setAssetColours((current) => ({ ...current, [assetId]: colour }));

  const fonts = useMemo(() => [...new Set([...document.front.layers, ...document.back.layers]
    .filter((layer) => layer.font_family).map((layer) => `${layer.font_family}|${layer.font_weight ?? 400}`))], [document]);
  useEffect(() => {
    fonts.forEach((key) => { const [family, weight] = key.split("|"); void loadCardFont(design.id, family, Number(weight)); });
  }, [design.id, fonts]);

  const patch = (id: string, change: Partial<Layer>, record = true) => update((current) => patchLayer(current, view.side, id, change), record);
  const remove = (id: string) => { update((current) => removeLayer(current, view.side, id)); setSelectedId(null); };

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.closest("input, textarea, select, [contenteditable='true']"))) return;
      const shortcut = undoShortcut(event);
      if (shortcut) { event.preventDefault(); if (shortcut === "redo") working.redo(); else working.undo(); }
      else if ((event.key === "Delete" || event.key === "Backspace") && selected && !selected.locked && canEdit) {
        event.preventDefault(); remove(selected.id);
      } else if (event.key === "Escape") setSelectedId(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return <section className="grid gap-4" aria-label={title ?? "Card designer"}>
    <DesignActions design={design} saveStatus={working.status} saveError={working.error} canEdit={canEdit}
      flush={working.flush} onRetry={() => void working.retry()} onReload={() => void working.reload()} />
    <DesignToolbar design={design} document={document} view={view} onView={setView} canEdit={canEdit} flush={working.flush}
      onDocument={(change) => update(change)} onAdopt={(fresh) => { working.adopt(fresh); setSelectedId(null); }}
      onStock={(stock, width, height) => update((current) => applyStock(current, stock, width, height))}
      history={{ undo: working.undo, redo: working.redo, canUndo: working.canUndo, canRedo: working.canRedo }} />
    <div className="grid gap-4 lg:grid-cols-[17rem_minmax(0,1fr)_19rem]">
      <aside className="grid content-start gap-3 rounded-card border border-line bg-panel p-3">
        <SegmentedControl label="Panel" value={panel} fullWidth onChange={(value) => setPanel(value as Panel)}
          options={[{ value: "add", label: "Add" }, { value: "layers", label: "Layers" }, { value: "background", label: "Background" }]} />
        {panel === "add" ? <AddLayerMenu side={side} stock={document.stock} domain={design.domain} designId={design.id}
          readOnly={readOnly} onAssetColour={rememberColour}
          onAdd={(layer) => { update((current) => addLayer(current, view.side, layer)); setSelectedId(layer.id); }} /> : null}
        {panel === "add" && readOnly ? <p className="text-sm text-muted">You can view this design but not change it.</p> : null}
        {panel === "layers" ? <LayerList layers={side.layers} selectedId={selectedId} readOnly={readOnly} onSelect={setSelectedId}
          onPatch={(id, change) => patch(id, change)} onRemove={remove}
          onMove={(id, direction) => update((current) => moveLayer(current, view.side, id, direction))}
          onDuplicate={(id) => update((current) => {
            const result = duplicateLayer(current, view.side, id);
            if (result.id) setSelectedId(result.id);
            return result.document;
          })} /> : null}
        {panel === "background" ? <div className="grid gap-4">
          <BackgroundPicker designId={design.id} background={side.background} readOnly={readOnly} onAssetColour={rememberColour}
            onChange={(background) => update((current) => withSide(current, view.side, (value) => ({ ...value, background })))} />
          <WatermarkPicker designId={design.id} watermark={document.watermark} readOnly={readOnly} onAssetColour={rememberColour}
            onChange={(watermark) => update((current) => ({ ...current, watermark }))} />
        </div> : null}
      </aside>
      <div className="grid content-start justify-items-center gap-2">
        <div className="w-full max-w-[34rem]">
          <CardCanvas side={side} designId={design.id} values={values} mono={document.mono} selectedId={selectedId}
            gridMm={view.gridMm} showGrid={view.showGrid} readOnly={readOnly} onSelect={setSelectedId}
            onChange={(id, change, record) => patch(id, change, record)} onCheckpoint={working.checkpoint}
            label={`${view.side === "front" ? "Front" : "Back"} of the card, ${side.page_width_mm} by ${side.page_height_mm} mm`} />
        </div>
        <p className="text-xs text-muted">The dashed line is the 3 mm safe area: keep text inside it. Sample: {values.name}.</p>
      </div>
      <aside className="rounded-card border border-line bg-panel p-3" aria-label="Layer settings">
        {selected ? <>
          <h3 className="mb-3 text-sm font-semibold text-ink">{layerName(selected)}</h3>
          <LayerInspector side={side} layer={selected} designId={design.id} stock={document.stock} assetColours={assetColours}
            readOnly={readOnly} onChange={(change) => patch(selected.id, change)} />
        </> : <p className="text-sm text-muted">Select a layer on the card or in the Layers list to change it.</p>}
      </aside>
    </div>
  </section>;
}

import { t } from "@lingui/core/macro";
import { useId, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { Layer, Side, Watermark } from "./cardTypes";
import { SAFE_AREA_MM } from "./cardGeometry";
import { backgroundStyle, CardLayerView, useAssetUrl } from "./CardLayerView";
import { canvasWidth, moveSelection, pointerDeltaMm, resizeLayer, rotationAt, type Guide, type SpacingHint,
  type Zoom } from "./canvasMath";
import { CanvasOverlays, mm, type Readout } from "./CanvasOverlays";
import { layerName } from "./designDocument";
import { WatermarkView } from "./WatermarkView";
import { boundsOf, clickSelection, groupLabels, moveUnits, selectedLayers, type Patches } from "./selection";

type Drag = { mode: "move" | "resize" | "rotate"; start: { x: number; y: number }; layers: Layer[]; layer: Layer;
  moved: boolean; collapseTo: string[] | null };
type Feedback = { guides: Guide[]; hints: SpacingHint[]; readout: Readout | null };
const IDLE: Feedback = { guides: [], hints: [], readout: null };

/** The free canvas for one side. Click, Shift/Ctrl/Cmd-click and Alt-click select; dragging
 *  any selected layer moves the selection (snapping to the grid, guides and equal spacing;
 *  Alt drags freely); the corner handle resizes and the top handle rotates one layer. The
 *  keyboard (arrows, Alt+arrows, Delete …) is handled by the designer for the whole selection. */
export function CardCanvas({ side, designId, values, mono, stock, selection, gridMm, showGrid, zoom, onSelect, onPatch,
  onCheckpoint, readOnly, label, watermark }: {
  side: Side; designId: number; values: Record<string, string>; mono: boolean; stock: string; selection: string[];
  gridMm: number; showGrid: boolean; zoom: Zoom; onSelect: (ids: string[]) => void;
  onPatch: (patches: Patches, record: boolean) => void; onCheckpoint: () => void; readOnly: boolean; label: string;
  watermark?: Watermark;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const [room, setRoom] = useState({ width: 480, height: 560 });
  const [feedback, setFeedback] = useState<Feedback>(IDLE);
  const drag = useRef<Drag | null>(null);
  const pointerFocus = useRef(false);
  const hintId = useId();
  const backgroundUrl = useAssetUrl(designId, side.background.kind === "image" ? side.background.asset_id : null);
  useLayoutEffect(() => {
    const node = viewport.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) =>
      setRoom({ width: entry.contentRect.width, height: Math.max(240, window.innerHeight * 0.65) }));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const width = canvasWidth(room.width, room.height, side.page_width_mm, side.page_height_mm, zoom);
  const px = width / side.page_width_mm;
  const zoomed = zoom !== "fit" && zoom !== 1;
  const chosen = new Set(selection);
  const labels = groupLabels(side.layers);
  const single = selection.length === 1 ? side.layers.find((layer) => layer.id === selection[0]) ?? null : null;
  const bounds = selection.length > 1 ? boundsOf(selectedLayers(side, selection).filter((layer) => !layer.hidden)) : null;

  function onPointerMove(event: ReactPointerEvent) {
    const active = drag.current;
    if (!active || !active.layers.length) return;
    const { dx, dy } = pointerDeltaMm(active.start, { x: event.clientX, y: event.clientY }, px);
    if (!active.moved && Math.hypot(dx * px, dy * px) < 3) return;
    active.moved = true;
    const start = active.layer;
    if (active.mode === "move") {
      const result = moveSelection(side, active.layers, dx, dy, { gridMm, free: event.altKey });
      onPatch(result.patches, false);
      setFeedback({ guides: result.guides, hints: result.hints,
        readout: result.box ? { box: result.box, text: t`X ${mm(result.box.x)} · Y ${mm(result.box.y)} mm` } : null });
    } else if (active.mode === "resize") {
      const size = resizeLayer(side, start, dx, dy, { gridMm, stock, shift: event.shiftKey, free: event.altKey });
      onPatch({ [start.id]: size }, false);
      setFeedback({ guides: [], hints: [], readout: { box: { x: start.x_mm, y: start.y_mm, w: size.w_mm, h: size.h_mm },
        text: t`W ${mm(size.w_mm)} × H ${mm(size.h_mm)} mm` } });
    } else {
      const rect = surface.current!.getBoundingClientRect();
      const centre = { x: rect.left + (start.x_mm + start.w_mm / 2) * px, y: rect.top + (start.y_mm + start.h_mm / 2) * px };
      const rotation = rotationAt(start, centre, { x: event.clientX, y: event.clientY }, event.shiftKey);
      onPatch({ [start.id]: { rotation } }, false);
      setFeedback({ guides: [], hints: [], readout: { box: { x: start.x_mm, y: start.y_mm, w: start.w_mm, h: start.h_mm },
        text: `${Math.round(rotation)}°` } });
    }
  }

  function finish() {
    const active = drag.current;
    drag.current = null;
    pointerFocus.current = false;
    setFeedback(IDLE);
    // A plain click (no drag) inside a bigger selection narrows it to what was clicked.
    if (active && !active.moved && active.collapseTo) onSelect(active.collapseTo);
  }

  function begin(event: ReactPointerEvent, layer: Layer, mode: Drag["mode"]) {
    event.stopPropagation();
    pointerFocus.current = true;
    const additive = event.shiftKey || event.ctrlKey || event.metaKey;
    const next = mode === "move" ? clickSelection(side.layers, selection, layer.id, { additive, single: event.altKey }) : selection;
    if (next !== selection) onSelect(next);
    if (additive) return;
    const clicked = clickSelection(side.layers, [], layer.id, { single: event.altKey });
    const collapseTo = mode === "move" && next.length > clicked.length ? clicked : null;
    const units = readOnly ? [] : mode === "move" ? moveUnits(selectedLayers(side, next).filter((item) => !item.hidden))
      .filter((unit) => unit.every((item) => !item.locked)).flat() : layer.locked ? [] : [layer];
    if (units.length) {
      onCheckpoint();
      event.currentTarget.setPointerCapture?.(event.pointerId);
    }
    drag.current = { mode, start: { x: event.clientX, y: event.clientY }, layers: units, layer, moved: false, collapseTo };
  }

  const handle = "absolute grid h-11 w-11 touch-none place-items-center";
  const dot = "h-4 w-4 rounded-full border-2 border-white bg-accent-ink shadow";
  return <div ref={viewport} data-card-viewport="" tabIndex={zoomed ? 0 : undefined} role={zoomed ? "region" : undefined}
    aria-label={zoomed ? t`${label}, zoomed in. Scroll to see all of it.` : undefined}
    className={`w-full min-w-0 ${zoomed ? "max-h-[70vh] overflow-auto overscroll-contain rounded-card focus-visible:outline-2 focus-visible:outline-focus [scrollbar-gutter:stable]" : ""}`}>
    <div ref={surface} role="group" aria-label={label} data-card-canvas=""
      className="relative mx-auto select-none overflow-hidden rounded-[3.18mm] outline outline-1 outline-line"
      style={{ width, height: side.page_height_mm * px,
        ...backgroundStyle(mono ? { kind: "colour", colour: "#FFFFFF" } : side.background, backgroundUrl) }}
      onPointerMove={onPointerMove} onPointerUp={finish} onPointerCancel={finish}
      onPointerDown={(event) => { if (!(event.shiftKey || event.ctrlKey || event.metaKey)) onSelect([]); }}>
      {showGrid ? <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={{
        backgroundImage: "linear-gradient(to right, rgb(0 110 99 / 12%) 1px, transparent 1px), linear-gradient(to bottom, rgb(0 110 99 / 12%) 1px, transparent 1px)",
        backgroundSize: `${gridMm * px}px ${gridMm * px}px` }} /> : null}
      <WatermarkView watermark={watermark} widthMm={side.page_width_mm} heightMm={side.page_height_mm} px={px} mono={mono}
        designId={designId} />
      {!readOnly ? <div aria-hidden="true" className="pointer-events-none absolute border border-dashed border-accent-ink/40"
        style={{ inset: SAFE_AREA_MM * px }} /> : null}
      <span id={hintId} className="sr-only">{t`Arrow keys move the selection, Shift for 5 mm; Alt with arrows resizes. Shift-click adds to the selection; Alt-click picks one layer in a group.`}</span>
      {side.layers.map((layer) => {
        if (layer.hidden) return null;
        const selected = chosen.has(layer.id);
        const group = layer.group ? labels[layer.group] : null;
        return <div key={layer.id} role="button" tabIndex={readOnly ? -1 : 0} aria-describedby={hintId}
          aria-label={`${layerName(layer)} layer${layer.locked ? ", locked" : ""}${group ? `, group ${group}` : ""}`}
          aria-pressed={selected}
          className={`absolute touch-none focus-visible:outline-2 focus-visible:outline-focus ${selected ? "outline outline-2 outline-accent-ink" : ""} ${layer.locked ? "cursor-not-allowed" : "cursor-grab"}`}
          style={{ left: layer.x_mm * px, top: layer.y_mm * px, width: layer.w_mm * px, height: layer.h_mm * px,
            transform: `rotate(${layer.rotation}deg)`, opacity: (layer.opacity ?? 100) / 100 }}
          onPointerDown={(event) => begin(event, layer, "move")}
          onFocus={() => {
            if (!pointerFocus.current && !chosen.has(layer.id)) onSelect(clickSelection(side.layers, [], layer.id));
            pointerFocus.current = false;
          }}>
          <CardLayerView layer={layer} px={px} values={values} designId={designId} mono={mono} />
          {single?.id === layer.id && !readOnly && !layer.locked ? <>
            <span aria-hidden="true" className={`${handle} -bottom-[22px] -right-[22px] cursor-nwse-resize`}
              onPointerDown={(event) => begin(event, layer, "resize")}><span className={dot} /></span>
            <span aria-hidden="true" className={`${handle} -top-[34px] left-1/2 -translate-x-1/2 cursor-grab`}
              onPointerDown={(event) => begin(event, layer, "rotate")}><span className={dot} /></span>
          </> : null}
        </div>;
      })}
      <CanvasOverlays px={px} guides={feedback.guides} hints={feedback.hints} bounds={bounds} readout={feedback.readout} />
    </div>
  </div>;
}

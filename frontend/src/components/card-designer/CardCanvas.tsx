import { t } from "@lingui/core/macro";
import { useId, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { Guides, Layer, Side, SideName, Watermark } from "./cardTypes";
import { useAssetUrl } from "./CardLayerView";
import { CanvasLayerItem, type DragMode } from "./CanvasLayerItem";
import { GuidesOverlay } from "./GuidesOverlay";
import { SideBackground } from "./SideBackground";
import { marqueeHits, type MarqueeRect } from "./marquee";
import { canvasWidth, moveSelection, pointerDeltaMm, resizeLayer, rotationAt, type Guide, type SpacingHint,
  type Zoom, ZOOM_RANGE } from "./canvasMath";
import { CanvasOverlays, mm, type Readout } from "./CanvasOverlays";
import { CanvasFrame, RULER_PX } from "./CanvasFrame";
import type { PhotoState } from "./photoVariant";
import { WatermarkView } from "./WatermarkView";
import { boundsOf, clickSelection, groupLabels, moveUnits, selectedLayers, type Patches } from "./selection";

type Drag = { mode: DragMode; start: { x: number; y: number }; layers: Layer[]; layer: Layer;
  moved: boolean; collapseTo: string[] | null };
type Feedback = { guides: Guide[]; hints: SpacingHint[]; readout: Readout | null };
const IDLE: Feedback = { guides: [], hints: [], readout: null };

/** The free canvas for one side. Click, Shift/Ctrl/Cmd-click and Alt-click select; dragging
 *  any selected layer moves the selection (snapping to the grid, guides and equal spacing;
 *  Alt drags freely); the corner handle resizes and the top handle rotates one layer. The
 *  keyboard (arrows, Alt+arrows, Delete …) is handled by the designer for the whole selection. */
export function CardCanvas({ side, designId, values, mono, stock, selection, gridMm, showGrid, zoom, onSelect, onPatch,
  onCheckpoint, readOnly, label, watermark, guides, sideName = "front", onZoom, photoState, showRulers = false, onAddGuide }: {
  side: Side; designId: number; values: Record<string, string>; mono: boolean; stock: string; selection: string[];
  gridMm: number; showGrid: boolean; zoom: Zoom; onSelect: (ids: string[]) => void;
  onPatch: (patches: Patches, record: boolean) => void; onCheckpoint: () => void; readOnly: boolean; label: string;
  watermark?: Watermark; guides?: Guides; sideName?: SideName; onZoom?: (zoom: Zoom) => void; photoState?: PhotoState;
  /** Millimetre rulers on the top and left edges; clicking one calls `onAddGuide` with that position. */
  showRulers?: boolean; onAddGuide?: (axis: "x" | "y", atMm: number) => void;
}) {
  const viewport = useRef<HTMLDivElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const [room, setRoom] = useState({ width: 480, height: 560 });
  const [feedback, setFeedback] = useState<Feedback>(IDLE);
  const drag = useRef<Drag | null>(null);
  const [marquee, setMarquee] = useState<MarqueeRect | null>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ distance: number; zoom: number } | null>(null);
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
  // The frame (rulers, bleed band) takes room outside the card, so the card is sized for what is left.
  const bleedMm = readOnly ? 0 : guides?.bleed_mm ?? 0;
  const free = room.width - (showRulers ? RULER_PX : 0);
  const rough = canvasWidth(free, room.height, side.page_width_mm, side.page_height_mm, zoom) / side.page_width_mm;
  const width = canvasWidth(free - 2 * bleedMm * rough, room.height, side.page_width_mm, side.page_height_mm, zoom);
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
      const result = moveSelection(side, active.layers, dx, dy, { gridMm, free: event.altKey, guides });
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

  const currentZoom = () => (zoom === "fit" ? width / room.width : zoom);
  const clampZoom = (value: number) => Math.round(Math.min(ZOOM_RANGE[1], Math.max(ZOOM_RANGE[0], value)) * 100) / 100;
  function onWheel(event: React.WheelEvent) {
    if (!onZoom || !(event.ctrlKey || event.metaKey)) return;
    onZoom(clampZoom(currentZoom() * (event.deltaY < 0 ? 1.1 : 1 / 1.1)));
  }
  const toMm = (event: ReactPointerEvent) => {
    const rect = surface.current!.getBoundingClientRect();
    return { x: (event.clientX - rect.left) / px, y: (event.clientY - rect.top) / px };
  };
  function onSurfaceDown(event: ReactPointerEvent) {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinch.current = { distance: Math.hypot(a.x - b.x, a.y - b.y), zoom: currentZoom() };
      setMarquee(null);
      return;
    }
    const additive = event.shiftKey || event.ctrlKey || event.metaKey;
    if (!additive) onSelect([]);
    if (readOnly) return;
    const at = toMm(event);
    surface.current?.setPointerCapture?.(event.pointerId);
    setMarquee({ x0: at.x, y0: at.y, x1: at.x, y1: at.y, additive });
  }
  function onSurfaceMove(event: ReactPointerEvent) {
    if (pointers.current.has(event.pointerId)) pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pinch.current && pointers.current.size === 2 && onZoom) {
      const [a, b] = [...pointers.current.values()];
      onZoom(clampZoom(pinch.current.zoom * Math.hypot(a.x - b.x, a.y - b.y) / pinch.current.distance));
      return;
    }
    if (marquee) { const at = toMm(event); setMarquee({ ...marquee, x1: at.x, y1: at.y }); return; }
    onPointerMove(event);
  }
  function onSurfaceUp(event: ReactPointerEvent) {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (marquee) {
      const hits = marqueeHits(side.layers, marquee);
      if (hits.length) onSelect(marquee.additive ? [...new Set([...selection, ...hits])] : hits);
      setMarquee(null);
      return;
    }
    finish();
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

  return <div ref={viewport} data-card-viewport="" tabIndex={zoomed ? 0 : undefined} role={zoomed ? "region" : undefined}
    aria-label={zoomed ? t`${label}, zoomed in. Scroll to see all of it.` : undefined}
    className={`w-full min-w-0 ${zoomed ? "max-h-[70vh] overflow-auto overscroll-contain rounded-card focus-visible:outline-2 focus-visible:outline-focus [scrollbar-gutter:stable]" : ""}`}>
    <CanvasFrame widthMm={side.page_width_mm} heightMm={side.page_height_mm} px={px} bleedMm={bleedMm} rulers={showRulers}
      onAddGuide={readOnly ? undefined : onAddGuide}>
    <div ref={surface} role="group" aria-label={label} data-card-canvas=""
      className="relative select-none overflow-hidden rounded-[3.18mm] outline outline-1 outline-line"
      style={{ width, height: side.page_height_mm * px }}
      onPointerMove={onSurfaceMove} onPointerUp={onSurfaceUp} onPointerCancel={onSurfaceUp}
      onWheel={onWheel} onPointerDown={onSurfaceDown}>
      <SideBackground side={side} mono={mono} imageUrl={backgroundUrl} px={px} />
      {showGrid ? <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={{
        backgroundImage: "linear-gradient(to right, rgb(0 110 99 / 12%) 1px, transparent 1px), linear-gradient(to bottom, rgb(0 110 99 / 12%) 1px, transparent 1px)",
        backgroundSize: `${gridMm * px}px ${gridMm * px}px` }} /> : null}
      <WatermarkView watermark={watermark} widthMm={side.page_width_mm} heightMm={side.page_height_mm} px={px} mono={mono}
        designId={designId} />
      {!readOnly ? <GuidesOverlay guides={guides} px={px} side={sideName} /> : null}
      {marquee ? <span aria-hidden="true" className="pointer-events-none absolute border border-accent-ink bg-accent-ink/10"
        style={{ left: Math.min(marquee.x0, marquee.x1) * px, top: Math.min(marquee.y0, marquee.y1) * px,
          width: Math.abs(marquee.x1 - marquee.x0) * px, height: Math.abs(marquee.y1 - marquee.y0) * px }} /> : null}
      <span id={hintId} className="sr-only">{t`Arrow keys move the selection, Shift for 5 mm; Alt with arrows resizes. Shift-click adds to the selection; Alt-click picks one layer in a group.`}</span>
      {side.layers.map((layer) => layer.hidden ? null : <CanvasLayerItem key={layer.id} layer={layer} px={px} values={values}
        designId={designId} mono={mono} photoState={photoState} selected={chosen.has(layer.id)} readOnly={readOnly}
        handles={single?.id === layer.id && !readOnly && !layer.locked} group={layer.group ? labels[layer.group] : null}
        hintId={hintId} onBegin={begin} onFocus={(item) => {
          if (!pointerFocus.current && !chosen.has(item.id)) onSelect(clickSelection(side.layers, [], item.id));
          pointerFocus.current = false;
        }} />)}
      <CanvasOverlays px={px} guides={feedback.guides} hints={feedback.hints} bounds={bounds} readout={feedback.readout} />
    </div>
    </CanvasFrame>
  </div>;
}

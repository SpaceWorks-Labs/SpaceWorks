import { useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";

import type { Layer, Side } from "./cardTypes";
import { clamp, clampToCard, round1, SAFE_AREA_MM, snap, snapToGuides } from "./cardGeometry";
import { backgroundStyle, CardLayerView, useAssetUrl } from "./CardLayerView";

type Drag = { id: string; mode: "move" | "resize" | "rotate"; startX: number; startY: number; layer: Layer };

/** The free canvas for one side: drag to move, the corner handle resizes, the top handle
 *  rotates; arrows nudge (Shift ×5) and Alt+arrows resize. Snaps to the grid, to other
 *  layers' edges and centres (with guides), and keeps layers inside the 3 mm safe area. */
export function CardCanvas({ side, designId, values, mono, selectedId, gridMm, showGrid, onSelect, onChange,
  onCheckpoint, readOnly, label }: {
  side: Side; designId: number; values: Record<string, string>; mono: boolean; selectedId: string | null;
  gridMm: number; showGrid: boolean; onSelect: (id: string | null) => void;
  onChange: (id: string, patch: Partial<Layer>, record: boolean) => void; onCheckpoint: () => void;
  readOnly: boolean; label: string;
}) {
  const surface = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(480);
  const [guides, setGuides] = useState<{ axis: "x" | "y"; at: number }[]>([]);
  const drag = useRef<Drag | null>(null);
  const backgroundUrl = useAssetUrl(designId, side.background.kind === "image" ? side.background.asset_id : null);
  useLayoutEffect(() => {
    const node = surface.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const px = width / side.page_width_mm;

  function onPointerMove(event: ReactPointerEvent) {
    const active = drag.current;
    if (!active) return;
    const dx = (event.clientX - active.startX) / px, dy = (event.clientY - active.startY) / px;
    const start = active.layer;
    if (active.mode === "move") {
      const snapped = snapToGuides(side, start, snap(start.x_mm + dx, gridMm), snap(start.y_mm + dy, gridMm));
      const clamped = clampToCard(side, start, snapped.x, snapped.y);
      setGuides(snapped.guides);
      onChange(start.id, { x_mm: clamped.x, y_mm: clamped.y }, false);
    } else if (active.mode === "resize") {
      onChange(start.id, { w_mm: clamp(snap(start.w_mm + dx, gridMm / 2), 1, side.page_width_mm - start.x_mm),
        h_mm: clamp(snap(start.h_mm + dy, gridMm / 2), 0.5, side.page_height_mm - start.y_mm) }, false);
    } else {
      const bounds = surface.current!.getBoundingClientRect();
      const cx = bounds.left + (start.x_mm + start.w_mm / 2) * px, cy = bounds.top + (start.y_mm + start.h_mm / 2) * px;
      let angle = Math.atan2(event.clientY - cy, event.clientX - cx) * 180 / Math.PI + 90;
      const qr = start.kind === "desk_qr" || start.kind === "verify_qr";
      angle = qr || event.shiftKey ? Math.round(angle / (qr ? 90 : 15)) * (qr ? 90 : 15) : round1(angle);
      onChange(start.id, { rotation: ((angle % 360) + 360) % 360 }, false);
    }
  }

  function begin(event: ReactPointerEvent, layer: Layer, mode: Drag["mode"]) {
    event.stopPropagation();
    onSelect(layer.id);
    if (readOnly || layer.locked) return;
    onCheckpoint();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { id: layer.id, mode, startX: event.clientX, startY: event.clientY, layer };
  }

  function nudge(event: KeyboardEvent, layer: Layer) {
    const steps: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    const step = steps[event.key];
    if (!step || readOnly || layer.locked) return;
    event.preventDefault();
    const size = event.shiftKey ? 5 : 1;
    if (event.altKey) {
      onChange(layer.id, { w_mm: Math.max(1, round1(layer.w_mm + step[0] * size)), h_mm: Math.max(0.5, round1(layer.h_mm + step[1] * size)) }, true);
      return;
    }
    const next = clampToCard(side, layer, round1(layer.x_mm + step[0] * size), round1(layer.y_mm + step[1] * size));
    onChange(layer.id, { x_mm: next.x, y_mm: next.y }, true);
  }

  return <div ref={surface} role="group" aria-label={label}
    className="relative w-full touch-none select-none overflow-hidden rounded-[3.18mm] shadow-none outline outline-1 outline-line"
    style={{ aspectRatio: `${side.page_width_mm} / ${side.page_height_mm}`, ...backgroundStyle(mono ? { kind: "colour", colour: "#FFFFFF" } : side.background, backgroundUrl) }}
    onPointerMove={onPointerMove} onPointerUp={() => { drag.current = null; setGuides([]); }}
    onPointerCancel={() => { drag.current = null; setGuides([]); }} onPointerDown={() => onSelect(null)}>
    {showGrid ? <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={{
      backgroundImage: "linear-gradient(to right, rgb(0 110 99 / 12%) 1px, transparent 1px), linear-gradient(to bottom, rgb(0 110 99 / 12%) 1px, transparent 1px)",
      backgroundSize: `${gridMm * px}px ${gridMm * px}px` }} /> : null}
    {!readOnly ? <div aria-hidden="true" className="pointer-events-none absolute border border-dashed border-accent-ink/40"
      style={{ inset: SAFE_AREA_MM * px }} /> : null}
    {side.layers.map((layer) => layer.hidden ? null : <div key={layer.id} role="button" tabIndex={readOnly ? -1 : 0}
      aria-label={`${layer.name || layer.kind.replace("_", " ")} layer${layer.locked ? ", locked" : ""}. Arrow keys move it; Alt with arrows resizes.`}
      aria-pressed={selectedId === layer.id}
      className={`absolute focus-visible:outline-2 focus-visible:outline-focus ${selectedId === layer.id ? "outline outline-2 outline-accent-ink" : ""} ${layer.locked ? "cursor-not-allowed" : "cursor-grab"}`}
      style={{ left: layer.x_mm * px, top: layer.y_mm * px, width: layer.w_mm * px, height: layer.h_mm * px,
        transform: `rotate(${layer.rotation}deg)`, opacity: (layer.opacity ?? 100) / 100 }}
      onPointerDown={(event) => begin(event, layer, "move")} onKeyDown={(event) => nudge(event, layer)}
      onFocus={() => onSelect(layer.id)}>
      <CardLayerView layer={layer} px={px} values={values} designId={designId} mono={mono} />
      {selectedId === layer.id && !readOnly && !layer.locked ? <>
        <span aria-hidden="true" onPointerDown={(event) => begin(event, layer, "resize")}
          className="absolute -bottom-2 -right-2 h-4 w-4 cursor-nwse-resize rounded-full border-2 border-white bg-accent-ink" />
        <span aria-hidden="true" onPointerDown={(event) => begin(event, layer, "rotate")}
          className="absolute -top-5 left-1/2 h-4 w-4 -translate-x-1/2 cursor-grab rounded-full border-2 border-white bg-accent-ink" />
      </> : null}
    </div>)}
    {guides.map((guide, index) => <span key={index} aria-hidden="true" className="pointer-events-none absolute bg-[#FF7447]"
      style={guide.axis === "x" ? { left: guide.at * px, top: 0, bottom: 0, width: 1 } : { top: guide.at * px, left: 0, right: 0, height: 1 }} />)}
  </div>;
}

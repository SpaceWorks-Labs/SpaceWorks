import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { Layer, LayerDocument } from "../layout";
import { CanvasLayer } from "./CanvasLayer";
import { keepOnPage, resizeFromCorner, rotationFrom, snapMove, type Box, type Corner, type Guide } from "./geometry";

export const MM_PX = 96 / 25.4;
export type Zoom = "fit" | 1 | 1.5 | 2;
type Gesture = { mode: "move" | "resize" | "rotate"; id: string; x: number; y: number; box: Box; corner?: Corner };

type Props = { document: LayerDocument; selectedId?: string; zoom: Zoom; values?: Record<string, string>;
  signatures?: Record<number, { name: string; title: string }>;
  onSelect: (id: string) => void; onBegin: () => void; onLive: (layers: Layer[]) => void;
  onChange: (layers: Layer[]) => void; onDelete: (id: string) => void; onDuplicate: (id: string) => void };

/** The design surface: drag, corner-resize and rotate with snapping guides; full keyboard control. */
export function DesignCanvas({ document, selectedId, zoom, values, signatures, onSelect, onBegin, onLive, onChange, onDelete, onDuplicate }: Props) {
  const surface = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const [guides, setGuides] = useState<Guide[]>([]);
  const [fitWidth, setFitWidth] = useState(600);
  const holder = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = holder.current; if (!element) return;
    if (typeof ResizeObserver === "undefined") { setFitWidth(Math.max(240, element.clientWidth || 600)); return; }
    const observer = new ResizeObserver(([entry]) => setFitWidth(Math.max(240, entry.contentRect.width)));
    observer.observe(element); return () => observer.disconnect();
  }, []);
  const page = { width: document.page_width_mm, height: document.page_height_mm };
  const scale = zoom === "fit" ? fitWidth / page.width : MM_PX * zoom;
  const visible = document.layers.filter((layer) => !layer.hidden);
  const update = (id: string, patch: Partial<Layer>, live: boolean) => {
    const layers = document.layers.map((row) => row.id === id ? { ...row, ...patch } : row);
    if (live) onLive(layers); else onChange(layers);
  };

  function start(event: PointerEvent, layer: Layer, mode: Gesture["mode"], corner?: Corner) {
    if (event.button !== 0) return;
    surface.current?.setPointerCapture(event.pointerId);
    onBegin();
    gesture.current = { mode, id: layer.id, x: event.clientX, y: event.clientY, corner,
      box: { x_mm: layer.x_mm, y_mm: layer.y_mm, width_mm: layer.width_mm, height_mm: layer.height_mm } };
  }
  function move(event: PointerEvent) {
    const active = gesture.current; const layer = active && document.layers.find((row) => row.id === active.id);
    if (!active || !layer) return;
    const dx = (event.clientX - active.x) / scale, dy = (event.clientY - active.y) / scale;
    if (active.mode === "move") {
      const moved = { ...active.box, x_mm: active.box.x_mm + dx, y_mm: active.box.y_mm + dy };
      const others = visible.filter((row) => row.id !== layer.id);
      // Alt (Option) turns snapping off for fine placement.
      const result = event.altKey ? { box: keepOnPage(moved, page), guides: [] } : snapMove(moved, others, page, 6 / scale);
      setGuides(result.guides); update(layer.id, result.box, true);
    } else if (active.mode === "resize" && active.corner) {
      update(layer.id, resizeFromCorner(active.box, active.corner, dx, dy, layer, page, event.shiftKey), true);
    } else if (active.mode === "rotate" && surface.current) {
      const bounds = surface.current.getBoundingClientRect();
      const center = { x: bounds.left + (active.box.x_mm + active.box.width_mm / 2) * scale, y: bounds.top + (active.box.y_mm + active.box.height_mm / 2) * scale };
      update(layer.id, { rotation: rotationFrom(center, { x: event.clientX, y: event.clientY }, layer, event.shiftKey) }, true);
    }
  }
  function end() { gesture.current = null; setGuides([]); }

  function keys(event: KeyboardEvent, layer: Layer) {
    const step = event.shiftKey ? 5 : 1;
    const arrows: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    const arrow = arrows[event.key];
    if ((event.key === "Delete" || event.key === "Backspace") && !layer.locked) { event.preventDefault(); onDelete(layer.id); return; }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") { event.preventDefault(); onDuplicate(layer.id); return; }
    if (layer.locked) return;
    if (arrow) {
      event.preventDefault(); onBegin();
      const box = { x_mm: layer.x_mm, y_mm: layer.y_mm, width_mm: layer.width_mm, height_mm: layer.height_mm };
      const next = event.ctrlKey || event.metaKey
        ? keepOnPage({ ...box, width_mm: Math.max(1, box.width_mm + arrow[0]), height_mm: Math.max(1, box.height_mm + arrow[1]) }, page)
        : keepOnPage({ ...box, x_mm: box.x_mm + arrow[0], y_mm: box.y_mm + arrow[1] }, page);
      update(layer.id, next, false);
    } else if (event.key === "[" || event.key === "]") {
      event.preventDefault(); onBegin();
      const delta = (event.key === "]" ? 1 : -1) * (layer.type.endsWith("qr") ? 90 : event.shiftKey ? 15 : 1);
      update(layer.id, { rotation: ((layer.rotation + delta + 540) % 360) - 180 }, false);
    }
  }

  return <div ref={holder} className="w-full overflow-auto rounded-control border border-line bg-panel p-3">
    <div ref={surface} className="relative mx-auto touch-none select-none shadow-sm" role="group" aria-label={t`Design canvas`}
      // The canvas shows printed paper, so it stays white in both themes.
      style={{ width: page.width * scale, height: page.height * scale, background: "#FFFFFF" }}
      onPointerMove={move} onPointerUp={end} onPointerCancel={end}>
      {visible.map((layer) => <CanvasLayer key={layer.id} layer={layer} scale={scale} selected={layer.id === selectedId}
        values={values} signature={layer.signature_slot ? signatures?.[layer.signature_slot] : undefined}
        onSelect={() => onSelect(layer.id)} onKeyDown={(event) => keys(event, layer)}
        onPointerDown={(event, mode, corner) => start(event, layer, mode, corner)} />)}
      {guides.map((guide) => <span key={`${guide.axis}-${guide.at}`} aria-hidden="true" className="pointer-events-none absolute bg-focus"
        style={guide.axis === "x" ? { left: guide.at * scale, top: 0, bottom: 0, width: 1 } : { top: guide.at * scale, left: 0, right: 0, height: 1 }} />)}
    </div>
  </div>;
}

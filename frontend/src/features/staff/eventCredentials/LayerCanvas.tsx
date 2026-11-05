import { useRef } from "react";
import { snapMillimetres } from "../../../components/print-layout/positionedLayout";
import type { LayerDocument } from "./layout";
import { mergeTags } from "./badgeStocks";

/** `values` fills the merge tags for a preview (the badge short/long name sample); the stored text keeps its tags. */
export function LayerCanvas({ document, onChange, values }: { document: LayerDocument; onChange: (value: LayerDocument) => void;
  values?: Record<string, string> }) {
  const surface = useRef<HTMLDivElement>(null);
  const drag = useRef<{ id: string; x: number; y: number; left: number; top: number } | null>(null);
  function move(id: string, x: number, y: number) {
    onChange({ ...document, layers: document.layers.map((layer) => {
      if (layer.id !== id) return layer;
      const center = (document.page_width_mm-layer.width_mm)/2;
      return { ...layer, x_mm: Math.abs(x-center) <= 1 ? center : snapMillimetres(x, 1, document.page_width_mm-layer.width_mm),
        y_mm: snapMillimetres(y, 1, document.page_height_mm-layer.height_mm) };
    }) });
  }
  return <div ref={surface} className="relative w-full touch-none overflow-hidden rounded-control border border-line bg-panel" role="group" aria-label="Drag or use arrow keys to move layers"
    style={{ aspectRatio: `${document.page_width_mm}/${document.page_height_mm}` }}
    onPointerMove={(event) => { const active = drag.current; const bounds = surface.current?.getBoundingClientRect();
      if (active && bounds) move(active.id, active.left+(event.clientX-active.x)/bounds.width*document.page_width_mm,
        active.top+(event.clientY-active.y)/bounds.height*document.page_height_mm); }}
    onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
    {document.layers.map((layer) => <button key={layer.id} type="button" className="absolute min-h-11 min-w-11 overflow-hidden rounded-control border border-line bg-surface text-xs text-ink focus-visible:outline-2 focus-visible:outline-focus"
      aria-label={`Move ${layer.type === "text" ? layer.text : layer.type} layer`}
      style={{ left: `${layer.x_mm/document.page_width_mm*100}%`, top: `${layer.y_mm/document.page_height_mm*100}%`,
        width: `${layer.width_mm/document.page_width_mm*100}%`, height: `${layer.height_mm/document.page_height_mm*100}%` }}
      onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId);
        drag.current = { id: layer.id, x: event.clientX, y: event.clientY, left: layer.x_mm, top: layer.y_mm }; }}
      onKeyDown={(event) => { const shifts: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
        const shift = shifts[event.key]; if (shift) { event.preventDefault(); move(layer.id, layer.x_mm+shift[0], layer.y_mm+shift[1]); } }}>
      {layer.type === "text" ? (values ? mergeTags(layer.text ?? "", values) : layer.text) : layer.type.replace(/_/g, " ")}
    </button>)}
  </div>;
}

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { CircuitBoard, Download, Layers, Maximize, ZoomIn, ZoomOut } from "lucide-react";
import { currentTheme } from "../../../lib/theme";
import type { BoardLayer, KicadViewer } from "../../../vendor/kicanvas/kicanvas-entry";
import type { KicadVariant } from "./kicadCheck";

const LAYERS: { key: BoardLayer; label: string }[] = [
  { key: "top_copper", label: "Top copper" }, { key: "bottom_copper", label: "Bottom copper" },
  { key: "silkscreen", label: "Silkscreen" }, { key: "edge_cuts", label: "Board outline" }];

function webgl2() {
  try { return Boolean(document.createElement("canvas").getContext("webgl2")); } catch { return false; }
}

function reducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** Read-only KiCad drawing. The renderer loads on demand; any failure shows the download card. */
export default function KicadCanvas({ text, variant, filename, download }: {
  text: string; variant: KicadVariant; filename: string; download: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<KicadViewer | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "failed" | "no-webgl">("loading");
  const [hidden, setHidden] = useState<BoardLayer[]>([]);
  useEffect(() => {
    if (variant === "pcb" && !webgl2()) { setState("no-webgl"); return; }
    let disposed = false;
    setState("loading");
    void import("../../../vendor/kicanvas/kicanvas-entry")
      .then(({ mountKicad }) => mountKicad(host.current!, { text, variant, theme: currentTheme() }))
      .then(mounted => {
        if (disposed) { mounted.dispose(); return; }
        viewer.current = mounted; setState("ready");
      })
      .catch(() => { if (!disposed) setState("failed"); });
    return () => { disposed = true; viewer.current?.dispose(); viewer.current = null; };
  }, [text, variant]);
  const kind = variant === "pcb" ? "PCB" : "Schematic";
  const zoom = (step: 1 | -1) => viewer.current?.zoom(step, { animate: !reducedMotion() });
  const keys = (event: KeyboardEvent) => {
    if (event.key === "+" || event.key === "=") { event.preventDefault(); zoom(1); }
    else if (event.key === "-") { event.preventDefault(); zoom(-1); }
    else if (event.key === "0") { event.preventDefault(); viewer.current?.fit(); }
  };
  const toggle = (layer: BoardLayer) => {
    const next = hidden.includes(layer) ? hidden.filter(value => value !== layer) : [...hidden, layer];
    setHidden(next); viewer.current?.setLayerVisible(layer, !next.includes(layer));
  };
  if (state === "failed" || state === "no-webgl") return <div role="status" className="grid gap-3 rounded-xl border border-line bg-panel p-4">
    <p className="flex items-center gap-2 text-sm text-ink"><CircuitBoard aria-hidden size={20} />
      We couldn't preview this KiCad file. Download it to open in KiCad.</p>
    {state === "no-webgl" ? <p className="text-sm text-muted">Your browser can't draw boards.</p> : null}
    <button type="button" className="desk-button min-h-11 w-fit gap-2" onClick={download}><Download aria-hidden size={20} />Download original</button>
  </div>;
  return <figure className="grid gap-3">
    <div className="flex flex-wrap items-center gap-2" role="toolbar" aria-label={`${kind} preview controls`}>
      <button type="button" className="desk-button min-h-11 gap-2" disabled={state !== "ready"} onClick={() => viewer.current?.fit()}>
        <Maximize aria-hidden size={18} />Fit <kbd className="text-xs text-muted">0</kbd></button>
      <button type="button" className="desk-button min-h-11 gap-2" disabled={state !== "ready"} onClick={() => zoom(1)}>
        <ZoomIn aria-hidden size={18} />Zoom in <kbd className="text-xs text-muted">+</kbd></button>
      <button type="button" className="desk-button min-h-11 gap-2" disabled={state !== "ready"} onClick={() => zoom(-1)}>
        <ZoomOut aria-hidden size={18} />Zoom out <kbd className="text-xs text-muted">−</kbd></button>
      {variant === "pcb" ? <details className="relative">
        <summary className="desk-button min-h-11 cursor-pointer gap-2"><Layers aria-hidden size={18} />Layers</summary>
        <fieldset className="absolute z-10 mt-2 grid gap-1 rounded-xl border border-line bg-panel p-3 shadow-lg" disabled={state !== "ready"}>
          <legend className="sr-only">Visible board layers</legend>
          {LAYERS.map(layer => <label key={layer.key} className="flex min-h-11 items-center gap-3 text-sm">
            <input type="checkbox" checked={!hidden.includes(layer.key)} onChange={() => toggle(layer.key)} />{layer.label}</label>)}
        </fieldset></details> : null}
    </div>
    <div ref={host} role="img" aria-label={`${kind} preview of ${filename}`} tabIndex={0} onKeyDown={keys}
      className="h-96 w-full overflow-hidden rounded-xl border border-line bg-panel focus-visible:outline-2 focus-visible:outline-offset-2" />
    {state === "loading" ? <p role="status" className="text-sm text-muted">Preparing the drawing…</p> : null}
    {variant === "sch" ? <figcaption className="text-sm text-muted">Showing the top sheet; sub-sheets need the full project.</figcaption> : null}
  </figure>;
}

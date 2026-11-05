// Crop a card photo to the design's photo frame before it is uploaded (SPEC §6, #132f).
// Drag (or use the arrow keys) to move the picture, the slider (or + and -) to zoom. The
// result is drawn on a canvas in the browser, so the original file is never uploaded.
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { Modal } from "../ui/Modal";
import { clampView, cropRect, initialView, MAX_ZOOM, MIN_ZOOM, outputSize, pan, zoomTo, type CropView } from "./cropMath";

const PREVIEW_WIDTH = 280;

type Loaded = { source: CanvasImageSource; width: number; height: number; url: string };

function useLoadedImage(file: Blob | null) {
  const [image, setImage] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!file) { setImage(null); return; }
    const url = URL.createObjectURL(file);
    const element = new Image();
    let live = true;
    element.onload = () => { if (live) setImage({ source: element, width: element.naturalWidth, height: element.naturalHeight, url }); };
    element.onerror = () => { if (live) setError("That file couldn't be opened as a picture. Try a JPEG or PNG."); };
    element.src = url;
    setError(null);
    return () => { live = false; URL.revokeObjectURL(url); };
  }, [file]);
  return { image, error };
}

export function PhotoCropDialog({ file, aspect, onCancel, onDone, title = "Crop the photo" }: {
  file: Blob | null; aspect: number; onCancel: () => void; onDone: (cropped: Blob) => void; title?: string;
}) {
  const { image, error } = useLoadedImage(file);
  const [view, setView] = useState<CropView>({ zoom: 1, cx: 0, cy: 0 });
  const [busy, setBusy] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);
  const height = Math.round(PREVIEW_WIDTH / aspect);

  useEffect(() => { if (image) setView(initialView(image.width, image.height)); }, [image]);
  useEffect(() => {
    const context = canvas.current?.getContext?.("2d");
    if (!image || !context) return;
    const rect = cropRect(view, image.width, image.height, aspect);
    context.clearRect(0, 0, PREVIEW_WIDTH, height);
    context.drawImage(image.source, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, PREVIEW_WIDTH, height);
  }, [image, view, aspect, height]);

  const move = (dx: number, dy: number) => image && setView((current) =>
    pan(current, dx, dy, PREVIEW_WIDTH, image.width, image.height, aspect));
  const zoom = (value: number) => image && setView((current) => zoomTo(current, value, image.width, image.height, aspect));

  function onKey(event: KeyboardEvent) {
    const steps: Record<string, [number, number]> = { ArrowLeft: [8, 0], ArrowRight: [-8, 0], ArrowUp: [0, 8], ArrowDown: [0, -8] };
    if (steps[event.key]) { event.preventDefault(); move(...steps[event.key]); }
    else if (event.key === "+" || event.key === "=") { event.preventDefault(); zoom(view.zoom + 0.25); }
    else if (event.key === "-") { event.preventDefault(); zoom(view.zoom - 0.25); }
  }

  async function finish() {
    if (!image) return;
    setBusy(true);
    const rect = cropRect(clampView(view, image.width, image.height, aspect), image.width, image.height, aspect);
    const size = outputSize(rect);
    const output = document.createElement("canvas");
    output.width = size.width; output.height = size.height;
    const context = output.getContext("2d");
    if (!context) { setBusy(false); onDone(file!); return; }
    context.fillStyle = "#FFFFFF";
    context.fillRect(0, 0, size.width, size.height);
    context.drawImage(image.source, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, size.width, size.height);
    output.toBlob((blob) => { setBusy(false); if (blob) onDone(blob); }, "image/jpeg", 0.9);
  }

  return <Modal open={Boolean(file)} onClose={onCancel} title={title}
    footer={<div className="flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button min-h-11" onClick={onCancel}>Cancel</button>
      <button type="button" className="desk-button-primary min-h-11" disabled={!image || busy} onClick={() => void finish()}>
        {busy ? "Preparing…" : "Use this photo"}</button>
    </div>}>
    <div className="grid justify-items-center gap-3">
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      <canvas ref={canvas} width={PREVIEW_WIDTH} height={height} tabIndex={0} role="application" aria-roledescription="photo crop"
        aria-label="Photo crop. Drag or use the arrow keys to move the picture; plus and minus zoom."
        className="max-w-full cursor-move touch-none rounded-control border border-line bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        onKeyDown={onKey}
        onPointerDown={(event: PointerEvent<HTMLCanvasElement>) => {
          event.currentTarget.setPointerCapture?.(event.pointerId);
          drag.current = { x: event.clientX, y: event.clientY };
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          const scale = PREVIEW_WIDTH / Math.max(1, event.currentTarget.getBoundingClientRect().width || PREVIEW_WIDTH);
          move((event.clientX - drag.current.x) * scale, (event.clientY - drag.current.y) * scale);
          drag.current = { x: event.clientX, y: event.clientY };
        }}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} />
      <label className="grid w-full max-w-xs gap-1 text-xs font-semibold text-muted">
        <span>Zoom</span>
        <input type="range" min={MIN_ZOOM} max={MAX_ZOOM} step={0.05} value={view.zoom} disabled={!image}
          onChange={(event) => zoom(Number(event.target.value))} />
      </label>
      <p className="text-center text-xs text-muted">The frame matches the photo spot on the card. Only the cropped part is uploaded.</p>
    </div>
  </Modal>;
}

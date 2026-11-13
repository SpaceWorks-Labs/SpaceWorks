import { t } from "@lingui/core/macro";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { clamp, cssFilter, dragPan, filterOps, guidesFor, MAX_ZOOM, placement, SHAPES, type CoverEdits, type CropGuideId } from "./coverMath";

const GUIDE_LABEL = (id: CropGuideId) => ({ page: t`Event page`, cards: t`Cards`, social: t`Social share` })[id];

type Props = {
  src: string; natural: { width: number; height: number }; edits: CoverEdits; guides: boolean;
  /** A gesture is starting: remember the current edits for Undo. */
  onBegin: () => void;
  /** Live change during a gesture (not recorded separately in the undo history). */
  onLive: (patch: Partial<CoverEdits>) => void;
};

/**
 * The crop frame (B4): drag or arrow keys move the picture, the wheel, pinch or +/- zoom it. The picture is
 * drawn with a CSS transform built from the same model the canvas renderer uses, so what staff see is what saves.
 */
export function CoverCropStage({ src, natural, edits, guides, onBegin, onLive }: Props) {
  const frame = useRef<HTMLDivElement>(null);
  const helpId = useId();
  const [displayWidth, setDisplayWidth] = useState(0);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ distance: number; zoom: number } | null>(null);
  const latest = useRef(edits); latest.current = edits;
  const [dragging, setDragging] = useState(false);
  const { width: W, height: H } = SHAPES[edits.shape];
  const k = displayWidth ? displayWidth / W : 0;

  useEffect(() => {
    const node = frame.current;
    if (!node) return;
    const measure = () => setDisplayWidth(node.getBoundingClientRect().width);
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure); observer.observe(node);
    return () => observer.disconnect();
  }, []);
  // A wheel listener must be non-passive to keep the page from scrolling while zooming.
  useEffect(() => {
    const node = frame.current;
    if (!node) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      onBegin();
      onLive({ zoom: clamp(latest.current.zoom * Math.exp(-event.deltaY * 0.0015), 1, MAX_ZOOM) });
    };
    node.addEventListener("wheel", wheel, { passive: false });
    return () => node.removeEventListener("wheel", wheel);
  }, [onBegin, onLive]);

  const toFrame = (pixels: number) => (k ? pixels / k : 0);
  const down = (event: PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture?.(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 1) onBegin();
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinch.current = { distance: Math.hypot(a.x - b.x, a.y - b.y), zoom: latest.current.zoom };
    }
    setDragging(true);
  };
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const previous = pointers.current.get(event.pointerId);
    if (!previous) return;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size >= 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()];
      const ratio = Math.hypot(a.x - b.x, a.y - b.y) / Math.max(1, pinch.current.distance);
      onLive({ zoom: clamp(pinch.current.zoom * ratio, 1, MAX_ZOOM) });
      return;
    }
    onLive(dragPan(latest.current, natural.width, natural.height, toFrame(event.clientX - previous.x), toFrame(event.clientY - previous.y)));
  };
  const up = (event: PointerEvent<HTMLDivElement>) => {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (!pointers.current.size) setDragging(false);
  };
  const key = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = (event.shiftKey ? 0.05 : 0.01) * W;
    const moves: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (moves[event.key]) {
      event.preventDefault(); onBegin();
      onLive(dragPan(edits, natural.width, natural.height, ...moves[event.key]));
    } else if (["+", "=", "-", "_"].includes(event.key)) {
      event.preventDefault(); onBegin();
      onLive({ zoom: clamp(edits.zoom + (["+", "="].includes(event.key) ? 0.1 : -0.1), 1, MAX_ZOOM) });
    }
  };

  const place = placement(edits, natural.width, natural.height);
  const transform = `rotate(${place.angle}rad) translate(${place.panX * k}px, ${place.panY * k}px) scale(${place.flipX * place.scale * k}, ${place.flipY * place.scale * k})`;
  return <div className="grid gap-2">
    <div ref={frame} tabIndex={0} role="group" aria-roledescription={t`crop area`} aria-describedby={helpId}
      aria-label={t`Cover crop, ${SHAPES[edits.shape].ratio}. Zoom ${Math.round(edits.zoom * 100)} percent.`}
      className={`relative w-full touch-none select-none overflow-hidden rounded-xl border border-line bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
      style={{ aspectRatio: `${W} / ${H}` }} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onKeyDown={key}>
      {k ? <img src={src} alt="" draggable={false} className="pointer-events-none absolute left-1/2 top-1/2 max-w-none origin-center"
        style={{ width: natural.width, height: natural.height, marginLeft: -natural.width / 2, marginTop: -natural.height / 2, transform, filter: cssFilter(filterOps(edits)) }} /> : null}
      {dragging ? <div aria-hidden="true" className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
        {Array.from({ length: 9 }, (_, index) => <span key={index} className="border border-white/40" />)}</div> : null}
      {guides ? guidesFor(edits.shape).map(guide => <div key={guide.id} aria-hidden="true"
        className="pointer-events-none absolute border border-dashed border-white/90 shadow-[0_0_0_1px_rgb(0_0_0/0.35)]"
        style={{ left: `${guide.left * 100}%`, top: `${guide.top * 100}%`, width: `${guide.width * 100}%`, height: `${guide.height * 100}%` }}>
        <span className="absolute left-1 top-1 rounded bg-black/70 px-1.5 py-0.5 text-xs font-semibold text-white">{GUIDE_LABEL(guide.id)}</span>
      </div>) : null}
    </div>
    <p id={helpId} className="text-xs text-muted">{t`Drag to move the picture. Scroll, pinch or press + and − to zoom. Arrow keys nudge; hold Shift for bigger steps.`}</p>
  </div>;
}

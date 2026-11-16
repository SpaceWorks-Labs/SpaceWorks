import { useCallback, useEffect, useRef, type RefObject } from "react";

/** Where the pieces of one frame sit, measured once per resize (never per scroll). */
export type SequenceGeometry = { start: number; rest: number; distance: number; scale: number; offset: number };
export type SequenceFrame = {
  copyY: number; copyOpacity: number; copyInert: boolean;
  stageY: number; frameScale: number; figureOpacity: number; figureInert: boolean;
  revealOpacity: number; revealY: number; revealScale: number; revealInert: boolean;
  backdropOpacity: number;
};

// The staged ranges of the scroll, as fractions of the sequence: the copy lifts away first, the console
// rises into the middle, then the view moves through its surface and the overview settles in.
export const RANGES = { lift: [0, 0.25], rise: [0, 0.38], zoom: [0.55, 0.84], fade: [0.68, 0.84], reveal: [0.86, 1] } as const;
export const COPY_LIFT = 72;
export const PEEK = 120;
const MIN_WIDTH = "(min-width: 768px)";
const REDUCED = "(prefers-reduced-motion: reduce)";

export const clamp = (value: number) => Math.max(0, Math.min(1, value));
/** Smoothstep: eases in and out without overshoot, so nothing bounces. */
export const smoothstep = (value: number) => { const x = clamp(value); return x * x * (3 - 2 * x); };
const span = (progress: number, [from, to]: readonly [number, number]) => (progress - from) / (to - from);

/** Pure: one scroll position in, every transform and opacity out. */
export function sequenceFrame(progress: number, g: SequenceGeometry): SequenceFrame {
  const lift = clamp(span(progress, RANGES.lift));
  const rise = smoothstep(span(progress, RANGES.rise));
  const zoom = smoothstep(span(progress, RANGES.zoom));
  const figureOpacity = 1 - smoothstep(span(progress, RANGES.fade));
  const reveal = smoothstep(span(progress, RANGES.reveal));
  return {
    copyY: -COPY_LIFT * lift, copyOpacity: 1 - lift, copyInert: lift === 1,
    stageY: g.start + (g.rest - g.start) * rise, frameScale: 1 + (g.scale - 1) * zoom,
    figureOpacity, figureInert: figureOpacity === 0,
    revealOpacity: reveal, revealY: 32 * (1 - reveal), revealScale: 0.94 + 0.06 * reveal, revealInert: reveal === 0,
    backdropOpacity: rise,
  };
}

/** Progress through the pinned scene: 0 when it pins under the header, 1 when it is about to scroll away. */
export const sequenceProgress = (sequenceTop: number, g: Pick<SequenceGeometry, "distance" | "offset">) =>
  g.distance > 0 ? clamp((g.offset - sequenceTop) / g.distance) : 0;

/** Scale that carries the zoom target's nearer edges past the viewport's (6 % over, so no edge peeks). */
export function zoomScale(frame: DOMRect, target: DOMRect, width: number, height: number) {
  const cx = frame.left + frame.width / 2, cy = frame.top + frame.height / 2;
  const halfW = Math.min(cx - target.left, target.right - cx), halfH = Math.min(cy - target.top, target.bottom - cy);
  if (halfW <= 0 || halfH <= 0) return 1;
  return Math.max(width / (2 * halfW), height / (2 * halfH)) * 1.06;
}

type Parts = Record<"scene" | "copy" | "stage" | "frame" | "figure" | "content" | "reveal" | "backdrop", HTMLElement>;
function parts(root: HTMLElement): Parts | null {
  const found = {} as Parts;
  for (const key of ["scene", "copy", "stage", "frame", "figure", "content", "reveal", "backdrop"] as const) {
    const node = root.querySelector<HTMLElement>(`[data-seq="${key}"]`);
    if (!node) return null;
    found[key] = node;
  }
  return found;
}

/**
 * The pinned hero sequence. One passive scroll listener, throttled to one paint per animation frame;
 * geometry is measured on resize, on font load and when reduced motion changes. Everything is written
 * straight to the elements (transform and opacity only), never through React state, so scrolling never
 * re-renders. Off (a plain static page) under reduced motion, below 768px, or when the copy, the console
 * or the overview would not fit the screen. Returns `jumpToEnd` for the in-page skip link.
 */
export function useScrollSequence(ref: RefObject<HTMLElement | null>) {
  const geometry = useRef<SequenceGeometry | null>(null);
  const paintRef = useRef<() => void>(() => {});

  useEffect(() => {
    const root = ref.current;
    const els = root && parts(root);
    if (!root || !els || typeof window.matchMedia !== "function" || typeof window.requestAnimationFrame !== "function") return;
    const reduced = window.matchMedia(REDUCED), wide = window.matchMedia(MIN_WIDTH);
    let last: number | null = null, pending = false, frameId = 0;
    const moving = [els.copy, els.stage, els.frame, els.figure, els.reveal, els.backdrop];

    const paint = () => {
      pending = false;
      const g = geometry.current;
      if (!g) return;
      const progress = sequenceProgress(root.getBoundingClientRect().top, g);
      if (progress === last) return;
      last = progress;
      const f = sequenceFrame(progress, g);
      els.copy.style.transform = `translate3d(0, ${f.copyY}px, 0)`;
      els.copy.style.opacity = String(f.copyOpacity);
      els.stage.style.transform = `translate3d(0, ${f.stageY}px, 0)`;
      els.frame.style.transform = `scale(${f.frameScale})`;
      els.figure.style.opacity = String(f.figureOpacity);
      els.reveal.style.opacity = String(f.revealOpacity);
      els.reveal.style.transform = `translate3d(0, ${f.revealY}px, 0) scale(${f.revealScale})`;
      els.backdrop.style.opacity = String(f.backdropOpacity);
      els.copy.inert = f.copyInert;
      els.figure.inert = f.figureInert;
      els.reveal.inert = f.revealInert;
      root.toggleAttribute("data-moving", progress > 0 && progress < 1); // will-change only while it moves
    };
    const schedule = () => {
      if (geometry.current && !pending) { pending = true; frameId = window.requestAnimationFrame(paint); }
    };
    const reset = () => {
      geometry.current = null;
      root.removeAttribute("data-animated");
      root.removeAttribute("data-moving");
      for (const node of moving) { node.removeAttribute("style"); node.inert = false; }
      root.style.removeProperty("--sw-seq-copy-top");
      root.style.removeProperty("--sw-seq-start");
    };
    const measure = () => {
      reset();
      last = null;
      if (reduced.matches || !wide.matches) return;
      const header = document.querySelector<HTMLElement>(".sw-hub-header")?.offsetHeight ?? 0;
      root.style.setProperty("--sw-hub-header-h", `${header}px`);
      root.setAttribute("data-animated", "");
      const scene = els.scene.offsetHeight, copy = els.copy.offsetHeight, frame = els.frame.offsetHeight;
      const fits = scene >= copy + PEEK + 96 && frame <= scene - 48 && els.reveal.scrollHeight <= scene + 2;
      if (!fits) { reset(); return; }
      const start = scene - PEEK;
      root.style.setProperty("--sw-seq-copy-top", `${Math.max(24, (start - copy) / 2)}px`);
      root.style.setProperty("--sw-seq-start", `${start}px`);
      const frameRect = els.frame.getBoundingClientRect();
      geometry.current = {
        start, rest: (scene - frame) / 2, distance: root.offsetHeight - scene, offset: header,
        scale: zoomScale(frameRect, els.content.getBoundingClientRect(), window.innerWidth, scene),
      };
      paint();
    };

    paintRef.current = paint;
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", measure);
    reduced.addEventListener?.("change", measure);
    wide.addEventListener?.("change", measure);
    let live = true;
    document.fonts?.ready.then(() => { if (live) measure(); });
    measure();
    return () => {
      live = false;
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", measure);
      reduced.removeEventListener?.("change", measure);
      wide.removeEventListener?.("change", measure);
      reset();
      paintRef.current = () => {};
    };
  }, [ref]);

  /** Lands where the overview is fully in place, so focus can move into it. False when the page is static. */
  const jumpToEnd = useCallback(() => {
    const root = ref.current, g = geometry.current;
    if (!root || !g) return false;
    window.scrollTo({ top: window.scrollY + root.getBoundingClientRect().top - g.offset + g.distance, behavior: "instant" });
    paintRef.current();
    return true;
  }, [ref]);

  return { jumpToEnd };
}

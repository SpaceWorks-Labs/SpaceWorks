import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { eggsAllowed, useDelight, useReducedMotion } from "./DelightProvider";
import "./confetti.css";

// Brand palette tokens only: Maker Teal, Workshop Orange, Citron, Warm Yellow, Sky Blue. On a
// citron or yellow panel (a success or warn tone) those two would vanish, so the burst swaps them for
// the panel's own ink; the tone comes from the nearest `[data-tone]` (ResultPanel sets it).
const FULL = ["--color-accent", "--color-emphasis", "--color-success", "--color-warn", "--color-info"];
const LIGHT_TONES: Record<string, string> = { success: "--color-on-success", warn: "--color-on-warn" };
export function confettiPalette(tone: string | undefined) {
  const ink = tone ? LIGHT_TONES[tone] : undefined;
  return ink ? ["--color-accent", "--color-emphasis", "--color-info", ink] : FULL;
}
const SHAPES = ["square", "circle", "box"] as const;
const COUNT = 16;
// A fixed fan over the top half, so every burst looks the same and tests stay deterministic.
const PIECES = Array.from({ length: COUNT }, (_, index) => {
  const angle = (-165 + (150 * index) / (COUNT - 1)) * (Math.PI / 180);
  const reach = 64 + (index % 3) * 22;
  return { dx: Math.round(Math.cos(angle) * reach), dy: Math.round(Math.sin(angle) * reach), spin: (index % 2 ? 1 : -1) * (120 + index * 15),
    shape: SHAPES[index % SHAPES.length], delay: (index % 4) * 30 };
});

/**
 * A once-only, ~1.2 s burst of brand-colour shapes from where it is mounted (a return's success
 * card). Decorative: hidden from assistive tech, no pointer events, nothing under reduced motion,
 * and never on kiosk, scanner, checkout or payment paths.
 */
export function ReturnConfetti() {
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  const anchor = useRef<HTMLSpanElement>(null);
  const [origin, setOrigin] = useState<{ x: number; y: number; palette: string[] } | null>(null);
  const [done, setDone] = useState(false);
  const allowed = enabled && !reduced && eggsAllowed(window.location.pathname);
  useLayoutEffect(() => {
    if (!allowed) return;
    const box = anchor.current?.getBoundingClientRect();
    const tone = anchor.current?.closest<HTMLElement>("[data-tone]")?.dataset.tone;
    if (box) setOrigin({ x: box.left + box.width / 2, y: box.top, palette: confettiPalette(tone) });
    const timer = window.setTimeout(() => setDone(true), 1300);
    return () => window.clearTimeout(timer);
  }, [allowed]);
  if (!allowed || done) return null;
  return <span ref={anchor} aria-hidden="true" className="sw-confetti-anchor">
    {origin ? <span className="sw-confetti" style={{ left: origin.x, top: origin.y }}>
      {PIECES.map((piece, index) => <span key={index} className={`sw-confetti-piece sw-confetti-${piece.shape}`} style={{
        "--dx": `${piece.dx}px`, "--dy": `${piece.dy}px`, "--spin": `${piece.spin}deg`, "--piece": `rgb(var(${origin.palette[index % origin.palette.length]}))`,
        animationDelay: `${piece.delay}ms`,
      } as CSSProperties} />)}
    </span> : null}
  </span>;
}

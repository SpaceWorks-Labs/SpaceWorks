import { useEffect, useRef, useState, type CSSProperties } from "react";
import { BOX, boxGroundColour, ensureBoxCss } from "../boxOpen/shared";
import { HOVER_MS } from "../boxOpen/css";

/** Where the symbol sits inside each master's viewBox, as a fraction of it (lockups scale the 136 x 126 symbol from the origin). */
const SYMBOL_BOX = {
  symbol: { w: 136, h: 126, vw: 136, vh: 126 },
  stacked: { w: 136 * 1.0084, h: 126 * 1.0084, vw: 360, vh: 128 },
  horizontal: { w: 136 * 0.45714, h: 57.6, vw: 360, vh: 58 },
} as const;

const reduced = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };
const focusVisible = (target: EventTarget | null) => { try { return target instanceof Element && target.matches(":focus-visible"); } catch { return false; } };
/**
 * The hover/focus cycle laid over the symbol part of a mark: the box folds shut from the resting logo, then
 * opens back to it (`hov`, 2200 ms), so nothing snaps at either end. Starts on pointer-enter (mouse or pen, never
 * touch) or keyboard focus-visible of the host link/button (or the mark itself); once started it always finishes,
 * leaving mid-way does not cut it, and re-entering while it runs does not restart it.
 */
export function LogoBoxOverlay({ shape, width, height, offset, surface, oneColour }: {
  shape: keyof typeof SYMBOL_BOX; width: number; height: number; offset: number; surface: string; oneColour: boolean;
}) {
  ensureBoxCss();
  const box = SYMBOL_BOX[shape];
  const root = useRef<HTMLSpanElement>(null);
  const [playing, setPlaying] = useState(false);
  const running = useRef(false);
  const [ground, setGround] = useState<string | undefined>(undefined);

  useEffect(() => {
    const mark = root.current?.parentElement;
    if (!mark) return;
    const host = mark.closest("a, button") ?? mark;
    const start = () => { if (!running.current && !reduced()) { running.current = true; setGround(boxGroundColour(mark)); setPlaying(true); } };
    const onEnter = (event: Event) => { if ((event as PointerEvent).pointerType !== "touch") start(); };
    const onFocus = (event: Event) => { if (focusVisible(event.target)) start(); };
    const overlay = root.current;
    const onEnd = (event: Event) => { if (["sw-boxh-w", "sw-box412h-w"].includes((event as AnimationEvent).animationName)) { running.current = false; setPlaying(false); } };
    host.addEventListener("pointerenter", onEnter);
    host.addEventListener("focusin", onFocus);
    overlay?.addEventListener("animationend", onEnd);
    return () => { host.removeEventListener("pointerenter", onEnter); host.removeEventListener("focusin", onFocus); overlay?.removeEventListener("animationend", onEnd); };
  }, []);

  useEffect(() => {
    const mark = root.current?.parentElement;
    if (!playing || !mark) return;
    mark.setAttribute("data-logo-playing", "");
    const finish = () => { running.current = false; setPlaying(false); };
    const timer = window.setTimeout(finish, HOVER_MS + 250); // safety net if no animationend arrives
    return () => { window.clearTimeout(timer); mark.removeAttribute("data-logo-playing"); };
  }, [playing]);

  const mono = oneColour;
  return <span ref={root} className="sw-logo-box" aria-hidden="true"
    style={{ left: offset, top: offset, width: width * box.w / box.vw, height: height * box.h / box.vh }}>
    {playing ? <span className={`sw-box hov ${surface === "dark" ? "g-dark" : "g-light"}${mono ? " mono" : ""}`}
      style={{ display: "block", ...(ground ? { "--sw-ground": ground } : {}), ...(mono ? { color: surface === "dark" ? "#FFF4E8" : "#142C2A" } : {}) } as CSSProperties} dangerouslySetInnerHTML={{ __html: BOX }} /> : null}
  </span>;
}

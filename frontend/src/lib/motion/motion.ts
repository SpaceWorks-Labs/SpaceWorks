// Motion constants shared by every hook here. The CSS twins live in src/index.css (--sw-dur-*),
// keep the two in step: a JS exit timer shorter than its CSS exit animation would cut it off.
export const MOTION_MS = { fast: 120, base: 180, slow: 240, exit: 120 } as const;

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
}

/**
 * True only where animations really run. jsdom has no Web Animations API, so unit tests see
 * `false` and every exit unmounts immediately; reduced-motion users get the same instant path.
 */
export function canAnimate(): boolean {
  return typeof document !== "undefined" && typeof document.getAnimations === "function" && !prefersReducedMotion();
}

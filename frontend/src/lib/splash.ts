import { t } from "@lingui/core/macro";

/**
 * The cold-start splash. index.html paints a closed Space Works box before any script runs (so a slow
 * first load is never a blank page) and its CSS opens it (src/components/boxOpen, ~1.6 s, ending on the
 * exact brand symbol). This takes over once React has mounted: after the open it rises and shrinks
 * into the navbar logo (FLIP: measure the logo, animate transform only, ease-out, no fade), then the
 * splash backdrop fades and the real logo, already underneath in the same spot, takes over. A page
 * with no navbar logo: the box rises to the top centre and fades. It runs at most once per page
 * load: the element is gone afterwards, so client-side navigations never see it. Reduced motion:
 * the still open logo, then a quick fade.
 */
export const SPLASH_ID = "sw-splash";
export const SPLASH_TARGET_ATTR = "data-sw-logo-target";
const OPEN_MS = 1700;
const FLIGHT_MS = 520;
const FADE_MS = 200;
const TARGET_WAIT_MS = 3000;
const LOCKUP_SYMBOL = { width: 61.8462 / 360, height: 57.6 / 58 };

const HUB_PATH = /^\/(?:(?:spaces|features|docs)(?:\/|$))?$|^\/docs\//;

type Box = { left: number; top: number; width: number; height: number };

/** The symbol's box inside the navbar logo: a lockup's symbol is its left part, the stand-alone symbol is the whole svg. */
export function findLogoTarget(root: ParentNode = document): Box | null {
  for (const svg of root.querySelectorAll<SVGSVGElement>(`[${SPLASH_TARGET_ATTR}] svg`)) {
    const rect = svg.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    const lockup = (svg.viewBox?.baseVal?.width ?? 0) > 200;
    return lockup ? { left: rect.left, top: rect.top, width: rect.width * LOCKUP_SYMBOL.width, height: rect.height * LOCKUP_SYMBOL.height }
      : { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
  }
  return null;
}

const wait = (ms: number) => new Promise<void>(resolve => window.setTimeout(resolve, ms));
const frame = () => new Promise<void>(resolve => window.requestAnimationFrame(() => resolve()));

async function waitForTarget(deadline: number): Promise<Box | null> {
  for (;;) {
    const target = findLogoTarget();
    if (target || Date.now() >= deadline) return target;
    await frame();
  }
}

function reducedMotion() {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
}

export async function runSplash(): Promise<void> {
  const splash = document.getElementById(SPLASH_ID);
  if (!splash) return;
  const status = document.getElementById("sw-splash-status");
  if (status) status.textContent = t`Loading`;
  const done = () => { splash.remove(); status?.remove(); };
  const reduced = reducedMotion();
  const mark = splash.querySelector<HTMLElement>(".mark");
  const backdrop = splash.querySelector<HTMLElement>(".bg");
  try {
    if (!reduced) await wait(Math.max(0, OPEN_MS - performance.now()));
    const hub = HUB_PATH.test(window.location.pathname);
    const target = reduced || !hub ? null : await waitForTarget(Date.now() + TARGET_WAIT_MS);
    if (typeof splash.animate !== "function") return done();
    if (!reduced && mark && backdrop) {
      const from = mark.getBoundingClientRect();
      // No navbar logo: rise to the top centre at half size, fading as it goes.
      const to = target ?? { left: window.innerWidth / 2 - from.width / 4, top: 16, width: from.width / 2, height: from.height / 2 };
      const scale = to.height / from.height;
      const rise = mark.animate([
        { transform: "translate(0px, 0px) scale(1)", opacity: 1 },
        { transform: `translate(${to.left - from.left}px, ${to.top - from.top}px) scale(${scale})`, opacity: target ? 1 : 0 },
      ], { duration: FLIGHT_MS, easing: "cubic-bezier(0.22, 1, 0.36, 1)", fill: "forwards" });
      await rise.finished;
      // Landed: the real logo is underneath in this exact spot, so the backdrop can fade without a jump.
      await splash.animate([{ opacity: 1 }, { opacity: 0 }], { duration: FADE_MS, fill: "forwards" }).finished;
    } else {
      await splash.animate([{ opacity: 1 }, { opacity: 0 }], { duration: reduced ? 150 : FADE_MS, fill: "forwards" }).finished;
    }
  } catch { /* an interrupted animation still ends with the splash removed */ }
  done();
}

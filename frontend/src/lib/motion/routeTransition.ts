import { prefersReducedMotion } from "./motion";

// Route changes use View Transitions where they exist. Only the element marked [data-sw-main]
// animates (src/styles/motionRoute.css), so the sidebar and top bar stay put. The attribute that
// names it is set only for the length of a route transition, so it cannot disturb the theme
// switch (themeTransition.ts), which owns the whole-page snapshot. Navigation is never blocked:
// the commit always runs, and a timer settles the transition if the new page is slow to render.

export type RouteDirection = "forward" | "back" | "lateral" | "fade";
type Transition = { finished: Promise<unknown> };
type TransitionDocument = Document & { startViewTransition?: (update: () => Promise<void> | void) => Transition };

const SETTLE_MS = 160;
const START_MS = 400;
const parse = (value: string) => new URL(value, "http://sw.invalid");
const segments = (path: string) => path.split("/").filter(Boolean);

let pending: { resolve: () => void; timer: ReturnType<typeof setTimeout> } | null = null;

/** Search and hash changes stay on the same page: no transition, no focus move. */
export function isSamePage(from: string, to: string): boolean {
  return parse(from).pathname === parse(to).pathname;
}

/** Going deeper is "forward", up a level "back", a sibling "lateral"; kiosk and TV screens only fade. */
export function routeDirection(from: string, to: string): RouteDirection {
  if (typeof document !== "undefined" && document.querySelector(".sw-kiosk, .sw-tv")) return "fade";
  const a = segments(parse(from).pathname);
  const b = segments(parse(to).pathname);
  return b.length > a.length ? "forward" : b.length < a.length ? "back" : "lateral";
}

export function canTransitionRoute(from: string, to: string): boolean {
  if (typeof document === "undefined" || prefersReducedMotion()) return false;
  if (typeof (document as TransitionDocument).startViewTransition !== "function") return false;
  if (parse(to).origin !== parse(from).origin || isSamePage(from, to)) return false;
  // A theme switch in flight owns the page snapshot.
  return !/\bsw-theme-reveal/.test(document.documentElement.className);
}

/** Runs `commit` (the real navigation) inside a View Transition when allowed, otherwise just runs it. */
export function navigateWithTransition(commit: () => void, from: string, to: string): void {
  if (!canTransitionRoute(from, to)) { commit(); return; }
  const doc = document as TransitionDocument;
  const root = document.documentElement;
  const cleanUp = () => { root.removeAttribute("data-sw-vt"); root.removeAttribute("data-sw-nav"); };
  root.setAttribute("data-sw-vt", "route");
  root.setAttribute("data-sw-nav", routeDirection(from, to));
  let committed = false;
  const run = () => { if (!committed) { committed = true; commit(); } };
  try {
    const transition = doc.startViewTransition!(() => new Promise<void>(resolve => {
      run();
      pending = { resolve, timer: setTimeout(() => { pending = null; resolve(); }, SETTLE_MS) };
    }));
    transition.finished.then(cleanUp, cleanUp);
    // If the browser never calls back (hidden tab), navigate anyway.
    setTimeout(run, START_MS);
  } catch {
    cleanUp();
    run();
  }
}

/** Called once the new location has rendered. True when a View Transition was waiting for it. */
export function settleRouteTransition(): boolean {
  if (!pending) return false;
  clearTimeout(pending.timer);
  pending.resolve();
  pending = null;
  return true;
}

/** Fallback for navigations without a View Transition: replay a CSS fade-in on the content region. */
export function replayRouteEnter(direction: RouteDirection): void {
  if (typeof document === "undefined" || prefersReducedMotion()) return;
  const region = document.querySelector<HTMLElement>("[data-sw-main]");
  if (!region) return;
  region.setAttribute("data-sw-enter", direction);
  region.classList.remove("sw-route-enter");
  void region.offsetWidth;
  region.classList.add("sw-route-enter");
}

import type { ThemePreference } from "./theme";
import { chooseTheme } from "./theme";
import "./themeTransition.css";

// Light/dark switch, adapted from AGPL-3.0 code; the attribution is in NOTICE.
// Where View Transitions exist, the new theme grows from the toggle as a circle (soft-edged when
// the browser can animate a registered custom property inside a mask); elsewhere every colour
// cross-fades. Reduced-motion users get an instant switch. The theme is always applied, even when
// an animation API is missing or throws.

const FEATHER = 160;
const TIMING = { duration: 720, easing: "cubic-bezier(0.45, 0, 0.2, 1)" } as const;

type ViewTransition = { ready: Promise<void>; finished: Promise<void> };
type TransitionDocument = Document & { startViewTransition?: (update: () => void) => ViewTransition };

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function supportsFeather() {
  return typeof CSS !== "undefined" && typeof CSS.registerProperty === "function"
    && CSS.supports?.("mask-image", "radial-gradient(circle, #000, transparent)") === true;
}

function originOf(element?: HTMLElement | null) {
  if (!element) return { x: window.innerWidth - 40, y: 32 };
  const box = element.getBoundingClientRect();
  return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
}

function fade(theme: ThemePreference) {
  const root = document.documentElement;
  root.classList.add("sw-theme-fade");
  chooseTheme(theme);
  window.setTimeout(() => root.classList.remove("sw-theme-fade"), 460);
}

export function transitionTheme(theme: ThemePreference, element?: HTMLElement | null) {
  if (prefersReducedMotion()) { chooseTheme(theme); return; }
  const doc = document as TransitionDocument;
  if (typeof doc.startViewTransition !== "function") { fade(theme); return; }

  const root = document.documentElement;
  // A route transition in flight names the content region; the theme reveal needs one whole-page snapshot.
  root.removeAttribute("data-sw-vt");
  const { x, y } = originOf(element);
  const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y)) + FEATHER;
  const feathered = supportsFeather();
  const mode = feathered ? "sw-theme-reveal-soft" : "sw-theme-reveal";
  root.style.setProperty("--sw-reveal-x", `${x}px`);
  root.style.setProperty("--sw-reveal-y", `${y}px`);
  root.classList.add(mode);
  const cleanUp = () => {
    root.classList.remove("sw-theme-reveal", "sw-theme-reveal-soft");
    root.style.removeProperty("--sw-reveal-x");
    root.style.removeProperty("--sw-reveal-y");
  };

  let applied = false;
  const apply = () => { applied = true; chooseTheme(theme); };
  const recover = () => { if (!applied) apply(); cleanUp(); };
  try {
    const transition = doc.startViewTransition(apply);
    transition.ready.then(() => {
      // fill: "forwards" holds the final frame; without it the mask snaps back for one frame
      // before the transition tears down, flashing the old theme.
      root.animate?.(
        feathered
          ? { "--sw-reveal": ["0px", `${radius}px`] }
          : { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { ...TIMING, fill: "forwards", pseudoElement: "::view-transition-new(root)" },
      );
    }).catch(recover);
    transition.finished.then(cleanUp, recover);
  } catch {
    recover();
  }
}

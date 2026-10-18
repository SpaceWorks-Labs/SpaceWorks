import type { Theme } from "../../lib/theme";
import { chooseTheme } from "../../lib/theme";

export function revealTheme(theme: Theme, element: HTMLElement, enabled: boolean, reduced: boolean) {
  if (!enabled || reduced) { chooseTheme(theme); return; }
  if (!document.startViewTransition) {
    chooseTheme(theme);
    try { document.documentElement.animate?.([{ opacity: .94 }, { opacity: 1 }], { duration: 180, easing: "ease-out" }); }
    catch { /* The saved theme still applies when animation isn't supported. */ }
    return;
  }
  let applied = false;
  const apply = () => { applied = true; chooseTheme(theme); };
  try {
    const transition = document.startViewTransition(apply);
    void transition.ready.then(() => {
      const bounds = element.getBoundingClientRect();
      const x = bounds.x + bounds.width / 2, y = bounds.y + bounds.height / 2;
      const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
      // animate() is optional on older browsers even when view transitions are present.
      document.documentElement.animate?.({ clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 360, easing: "ease-out", pseudoElement: "::view-transition-new(root)" });
    }).catch(() => { if (!applied) apply(); });
    void transition.finished.catch(() => { if (!applied) apply(); });
  } catch { if (!applied) apply(); }
}

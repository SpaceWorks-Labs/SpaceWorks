import { useEffect, useState, type RefObject } from "react";

const REDUCED = "(prefers-reduced-motion: reduce)";

/**
 * Which `[data-step]` child of `ref` sits across the middle of the screen. The observer's root margin
 * shrinks the viewport to a thin band at its centre, so exactly the step being read is active.
 * Without IntersectionObserver (old browsers, tests) the first step stays active and the controls
 * still move it.
 */
export function useActiveStep(ref: RefObject<HTMLElement | null>) {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const list = ref.current;
    if (!list || typeof window.IntersectionObserver !== "function") return;
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.step ?? 0));
      }
    }, { rootMargin: "-45% 0px -45% 0px" });
    list.querySelectorAll("[data-step]").forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [ref]);
  return [active, setActive] as const;
}

/**
 * Reveal-on-scroll for every `[data-reveal]` inside `ref`, once each: an element is marked
 * `data-revealed` the first time its top crosses the lower eighth of the screen, and is never watched
 * again. The hiding CSS only applies under `[data-reveal-ready]`, which is set here, so without
 * JavaScript, without IntersectionObserver or under reduced motion everything is simply visible.
 */
export function useRevealOnScroll(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const root = ref.current;
    if (!root || typeof window.IntersectionObserver !== "function" || typeof window.matchMedia !== "function") return;
    if (window.matchMedia(REDUCED).matches) return;
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.setAttribute("data-revealed", "");
        observer.unobserve(entry.target);
      }
    }, { rootMargin: "0px 0px -12% 0px" });
    root.querySelectorAll("[data-reveal]").forEach(node => observer.observe(node));
    root.setAttribute("data-reveal-ready", "");
    return () => { observer.disconnect(); root.removeAttribute("data-reveal-ready"); };
  }, [ref]);
}

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { currentTheme, subscribeTheme } from "../../lib/theme";
import { PATCH } from "./NotFoundPatch";
import { useReducedMotion } from "./DelightProvider";
import "./patch.css";

/**
 * Patch standing beside a section's copy: the section's one bold moment (docs/brand/README.md,
 * "Patch, the mascot"). Decorative only (aria-hidden, no pointer events). It trots on the spot twice
 * the first time it scrolls into view, then stands still; under reduced motion it is a still frame
 * from the start. Uses the shipped light or dark walk sheet as supplied: never recoloured or flipped.
 * Never place it inside or beside the box symbol (so never over the tiled-symbol backgrounds).
 */
export function PatchMoment({ facing = "right", className = "" }: { facing?: "left" | "right"; className?: string }) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, () => "light" as const);
  const reduced = useReducedMotion();
  const node = useRef<HTMLSpanElement>(null);
  const [trot, setTrot] = useState(false);
  useEffect(() => {
    const target = node.current;
    if (reduced || !target || typeof window.IntersectionObserver !== "function") return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setTrot(true); observer.disconnect(); }
    }, { threshold: 0.6 });
    observer.observe(target);
    return () => observer.disconnect();
  }, [reduced]);
  const sheet = (facing === "left" ? PATCH.walkLeft : PATCH.walkRight)[theme];
  return <span ref={node} aria-hidden="true" data-patch-moment="" data-trot={trot && !reduced ? "" : undefined}
    className={`sw-patch-moment ${className}`} style={{ backgroundImage: `url(${sheet})` }} />;
}

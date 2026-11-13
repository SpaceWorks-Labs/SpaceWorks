import type { ReactNode } from "react";
import { MOTION_MS, usePresence } from "../../lib/motion";

/**
 * Animated show/hide for a region (sidebar "More", accordions). The wrapper with `id` always
 * exists so `aria-controls` keeps pointing somewhere; children are unmounted once closed, so
 * collapsed content is never reachable by Tab, and while closing the region is inert.
 */
export function Collapse({ open, id, className, children }: { open: boolean; id?: string; className?: string; children: ReactNode }) {
  const { present, closing, state, onAnimationEnd } = usePresence(open, MOTION_MS.fast);
  if (!present) return <div id={id} hidden />;
  return <div id={id} className={`sw-collapse ${className ?? ""}`} data-state={state} inert={closing} onAnimationEnd={onAnimationEnd}>
    <div className="sw-collapse-inner">{children}</div>
  </div>;
}

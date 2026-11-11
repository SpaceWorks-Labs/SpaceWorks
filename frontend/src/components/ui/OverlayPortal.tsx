import { createContext, useContext, useLayoutEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** True inside an overlay that already lives at the top of the document. */
export const OverlayPortalContext = createContext(false);

// Page-scoped context an overlay must keep when it leaves its place in the tree: kiosk sizing and
// DetailLayout's drawer width/stacking rules (layouts.css).
// Applied to a display:contents wrapper, so no box is added.
const CARRIED_CLASSES = ["sw-kiosk", "sw-detail-drawer", "sw-detail-drawer-640", "sw-detail-drawer-720"];

/**
 * Renders a fixed overlay (modal, drawer) at the end of <body>, so an ancestor that is a CSS
 * container (`@container`), transformed or filtered cannot become its containing block and shrink
 * it to that box. Tenant colours are inline custom properties on a page wrapper, so the nearest
 * value of each is copied across, as are the page classes above. An overlay opened from inside
 * another overlay stays inline: its parent already sits at the top of the document.
 */
export function OverlayPortal({ children }: { children: ReactNode }) {
  const nested = useContext(OverlayPortalContext);
  const anchor = useRef<HTMLSpanElement>(null);
  const host = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const target = host.current;
    if (nested || !target) return;
    const seen = new Set<string>();
    for (let node = anchor.current?.parentElement; node && node !== document.documentElement; node = node.parentElement) {
      for (let index = 0; index < node.style.length; index++) {
        const name = node.style[index];
        if (!name.startsWith("--") || seen.has(name)) continue;
        seen.add(name);
        target.style.setProperty(name, node.style.getPropertyValue(name));
      }
      CARRIED_CLASSES.forEach(name => { if (node!.classList.contains(name)) target.classList.add(name); });
    }
  });
  if (nested || typeof document === "undefined") return <>{children}</>;
  return <>
    <span ref={anchor} hidden />
    {createPortal(<div data-replay-block ref={host} style={{ display: "contents" }}>
      <OverlayPortalContext.Provider value={true}>{children}</OverlayPortalContext.Provider>
    </div>, document.body)}
  </>;
}

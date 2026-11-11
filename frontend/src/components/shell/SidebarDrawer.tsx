import { t } from "@lingui/core/macro";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { DetailDrawer } from "../ui";
import { OverlayPortalContext } from "../ui/OverlayPortal";

export function SidebarDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const layer = root.current;
    const backgrounds = Array.from(document.body.children).filter(node => !node.contains(layer)) as HTMLElement[];
    const previous = backgrounds.map(node => node.inert);
    backgrounds.forEach(node => { node.inert = true; });
    return () => backgrounds.forEach((node, index) => { node.inert = previous[index]; });
  }, [open]);
  if (!open) return null;
  return createPortal(<div data-replay-block ref={root} className="[&_[role=dialog]]:left-0 [&_[role=dialog]]:right-auto [&_[role=dialog]]:w-[85vw] [&_[role=dialog]]:max-w-80 [&_[role=dialog]>div]:min-h-0 [&_[role=dialog]>div]:overflow-hidden [&_[role=dialog]>div]:p-0">
    {/* Already portalled: the drawer renders inline here, inside the layer its inert handling protects. */}
    <OverlayPortalContext.Provider value={true}><DetailDrawer open title={t`Navigation`} onClose={onClose}>{children}</DetailDrawer></OverlayPortalContext.Provider>
  </div>, document.body);
}

import type { ReactNode } from "react";
import { useTransitionNavigate } from "../../lib/motion";

/** Keep layout tab links as real destinations, while navigating inside the portal. */
export function MemberSectionNavigation({ children }: { children: ReactNode }) {
  const navigate = useTransitionNavigate();
  return <div className="min-w-0" onClick={event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const anchor = (event.target as HTMLElement).closest("a");
    const href = anchor?.getAttribute("href");
    if (!anchor || anchor.target || anchor.hasAttribute("download") || !href?.startsWith("/") || href.startsWith("//")) return;
    event.preventDefault();
    void navigate(href);
  }}>{children}</div>;
}

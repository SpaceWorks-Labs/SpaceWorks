import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
export function InventoryDetailNavigation({ children }: { children: ReactNode }) {
 const location = useLocation(), navigate = useNavigate();
 return <div onClickCapture={event => {
   if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
   const anchor = (event.target as Element).closest("a");
   if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
   const href = anchor.getAttribute("href");
   if (!href?.startsWith("?")) return;
   event.preventDefault();
   navigate({ pathname: location.pathname, search: href });
 }}>{children}</div>;
}

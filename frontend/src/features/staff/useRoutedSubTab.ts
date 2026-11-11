import { useLocation, useNavigate } from "react-router-dom";
import { staffPathState } from "./staffTabs";

/**
 * A console tab's internal view kept in the URL path (0.12.0 row 15): `/m/lab/admin/shop/pos`,
 * `/admin/finance/disputes`. Every view can then be bookmarked, shared and reloaded. The
 * caller owns the list of views: an absent or unknown `segment` falls back to its default,
 * because some views appear only after a query settles (Finance's access check). The tab
 * itself must be listed in `TABS_WITH_SUBPATHS` (staffTabs.ts) so canonicalisation keeps it.
 */
export function useRoutedSubTab() {
  const location = useLocation();
  const navigate = useNavigate();
  const { subPath } = staffPathState(location.pathname, location.pathname.startsWith("/guest-admin"));
  const segment = subPath.split("/")[0] ?? "";
  const path = location.pathname.replace(/\/+$/, "");
  const base = subPath && path.endsWith(`/${subPath}`) ? path.slice(0, path.length - subPath.length - 1) : path;
  // Only the session context survives a switch; other parameters belong to the view they came from.
  const context = new URLSearchParams(location.search).get("context");
  const href = (key: string) => `${base}/${encodeURIComponent(key)}${context ? `?context=${encodeURIComponent(context)}` : ""}`;
  return { segment, href, select: (key: string) => { navigate(href(key)); } };
}

import { useContext } from "react";
import { useInRouterContext, useLocation } from "react-router-dom";

import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { AllowedTabsContext } from "../areaOverview/allowedTabsContext";
import { staffPathState, staffTabPath } from "../staffTabs";

export type StaffLinkQuery = Record<string, string | number | null | undefined>;

/**
 * A link to another staff tab in the console the viewer is already in: same space, same
 * console (space or platform session), with the deep-link query that tab reads on open
 * (`?machine=`, `?event=`, `?space=&booking=`, `?incident=`, `?item=`, `?id=` …).
 * Empty values are dropped so a missing id never produces `?machine=null`.
 */
export function staffHref(pathname: string, tab: string, query: StaffLinkQuery = {}, subPath = "") {
  const guest = pathname.startsWith("/guest-admin");
  const base = staffTabPath(tab, guest, staffPathState(pathname, guest).makerspaceSlug || null, false, subPath);
  const params = new URLSearchParams(Object.entries(query)
    .filter((entry): entry is [string, string | number] => entry[1] !== null && entry[1] !== undefined && entry[1] !== "")
    .map(([key, value]) => [key, String(value)]));
  const search = params.toString();
  return consoleSessionHref(search ? `${base}?${search}` : base);
}

/** `staffHref` bound to the current route, for components rendered inside the router. */
export function useStaffHref() {
  // Outside a router (isolated panels, embeds) the browser's own path stands in; a component's
  // router context never changes between renders, so the hook order stays stable.
  const pathname = useInRouterContext() ? useLocation().pathname : window.location.pathname; // eslint-disable-line react-hooks/rules-of-hooks
  return (tab: string, query?: StaffLinkQuery, subPath?: string) => staffHref(pathname, tab, query, subPath);
}

/**
 * Like `useStaffHref`, but answers `undefined` for a tab this person cannot open in the active
 * space (decision 224: a role never follows a link into an area it does not manage). The
 * caller then shows plain text, or nothing, instead of a link to a refusal.
 */
export function useCrossLink() {
  const href = useStaffHref();
  const allowed = useContext(AllowedTabsContext);
  // C30: a person link without the Members tab opens the member 360 drawer on the current tab
  // (ConsoleMemberActivity); the server still decides what that viewer may see.
  const location = useInRouterContext() ? useLocation() : window.location; // eslint-disable-line react-hooks/rules-of-hooks
  return (tab: string, query?: StaffLinkQuery, subPath?: string) => {
    if (allowed.includes(tab)) return href(tab, query, subPath);
    if (tab !== "members" || !query?.member) return undefined;
    const params = new URLSearchParams(location.search);
    params.set("member", String(query.member));
    return consoleSessionHref(`${location.pathname}?${params}`);
  };
}

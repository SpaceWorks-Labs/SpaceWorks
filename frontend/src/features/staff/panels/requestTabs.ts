export const REQUEST_TABS = ["pending", "accepted", "active", "history"] as const;
export type RequestTab = typeof REQUEST_TABS[number];
/** "all" stacks every queue the actor may see; the per-queue tabs stay the default. */
export type RequestView = RequestTab | "all";
export const requestTabLabels: Record<RequestView, string> = {
  pending: "Pending review", accepted: "Ready for handover", active: "Active loans", history: "History", all: "All queues",
};
// Mirrors the list endpoints' own authority (hardware_requests/queue_views.py): pending-requests is
// scoped by ACCEPT_REQUEST, and accepted-requests, active-loans and request-history all by
// ISSUE_REQUEST. A tab the server would 404 is never shown, so a reviewer is not probed into errors.
const TAB_ACTIONS: Record<RequestTab, readonly string[]> = {
  pending: ["accept_request"],
  accepted: ["issue_request"],
  active: ["issue_request"],
  history: ["issue_request"],
};
export function visibleRequestTabs(guestOnly: boolean, actions: readonly string[] = [], isSuperadmin = false): RequestTab[] {
  return REQUEST_TABS.filter(tab => (tab !== "pending" && tab !== "active" || !guestOnly)
    && (isSuperadmin || TAB_ACTIONS[tab].some(action => actions.includes(action))));
}
/** Read legacy links without rewriting them; only an explicit tab click canonicalises the URL. */
export function resolveRequestTab(values: Record<string, string>, visible: RequestTab[]): RequestView | "resolve-id" | undefined {
  if (values.queue === "all" && visible.length > 1) return "all";
  if (values.queue) return visible.includes(values.queue as RequestTab) ? values.queue as RequestTab : visible[0];
  if (values.id) return "resolve-id";
  if (values.history === "true" && visible.includes("history")) return "history";
  const paged = REQUEST_TABS.filter(tab => Number(values[`${tab}Page`]) > 1);
  if (paged.length === 1 && visible.includes(paged[0])) return paged[0];
  return visible[0];
}
export function requestTabHref(pathname: string, search: string, tab: RequestView) {
  const params = new URLSearchParams(search);
  params.set("queue", tab); params.delete("history"); params.delete("request"); params.delete("requestView");
  REQUEST_TABS.forEach(key => params.delete(`${key}Page`));
  return `${pathname}?${params}`;
}

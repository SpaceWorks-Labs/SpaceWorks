export const REQUEST_TABS = ["pending", "accepted", "active", "history"] as const;
export type RequestTab = typeof REQUEST_TABS[number];
export const requestTabLabels: Record<RequestTab, string> = {
  pending: "Pending review", accepted: "Ready for handover", active: "Active loans", history: "History",
};
export function visibleRequestTabs(guestOnly: boolean, actions: readonly string[] = [], isSuperadmin = false): RequestTab[] {
  return REQUEST_TABS.filter(tab => (tab !== "pending" && tab !== "active" || !guestOnly)
    && (isSuperadmin || actions.includes(tab === "pending" ? "accept_request" : "issue_request")));
}
/** Read legacy links without rewriting them; only an explicit tab click canonicalises the URL. */
export function resolveRequestTab(values: Record<string, string>, visible: RequestTab[]): RequestTab | "resolve-id" | undefined {
  if (values.queue) return visible.includes(values.queue as RequestTab) ? values.queue as RequestTab : visible[0];
  if (values.id) return "resolve-id";
  if (values.history === "true" && visible.includes("history")) return "history";
  const paged = REQUEST_TABS.filter(tab => Number(values[`${tab}Page`]) > 1);
  if (paged.length === 1 && visible.includes(paged[0])) return paged[0];
  return visible[0];
}
export function requestTabHref(pathname: string, search: string, tab: RequestTab) {
  const params = new URLSearchParams(search);
  params.set("queue", tab); params.delete("history"); params.delete("request"); params.delete("requestView");
  REQUEST_TABS.forEach(key => params.delete(`${key}Page`));
  return `${pathname}?${params}`;
}

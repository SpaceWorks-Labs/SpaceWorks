import { usePaginatedQuery } from "../../../lib/usePaginatedQuery";
import type { HardwareRequest } from "./Queues";
import { REQUEST_TABS, resolveRequestTab, type RequestTab } from "./requestTabs";

export function useRequestQueues(makerspaceId: number, values: Record<string, string>, visible: RequestTab[], search: string,
  setPage: (page: number, key: string) => void) {
  values = { ...values, id: values.id || (!values.queue ? values.request : "") };
  const resolved = resolveRequestTab(values, visible);
  const probing = resolved === "resolve-id";
  const options = (tab: RequestTab, key: string, endpoint: string) => ({
    key: [key, makerspaceId], path: `/admin/makerspace/${makerspaceId}/${endpoint}`,
    id: values.id, page: probing ? 1 : Number(values[`${tab}Page`]),
    ordering: probing ? "" : values.ordering, search: probing ? "" : search,
    onPageChange: (page: number) => setPage(page, `${tab}Page`), resetKey: String(makerspaceId),
    enabled: visible.includes(tab) && (probing || resolved === tab),
  });
  // Keep the established query-key prefixes so accept, issue, return and renew refresh these lists.
  const pending = usePaginatedQuery<HardwareRequest>(options("pending", "pending", "pending-requests"));
  const accepted = usePaginatedQuery<HardwareRequest>(options("accepted", "accepted", "accepted-requests"));
  const active = usePaginatedQuery<HardwareRequest>(options("active", "active", "active-loans"));
  const history = usePaginatedQuery<HardwareRequest>(options("history", "request-history", "request-history"));
  const queries = { pending, accepted, active, history };
  const probes = visible.map(tab => queries[tab]);
  const finding = probing && probes.some(query => query.isPending || query.isPlaceholderData);
  const found = probing && !finding ? REQUEST_TABS.find(tab => visible.includes(tab) && queries[tab].results.length > 0) : undefined;
  const probeError = probing && !finding && !found && probes.some(query => query.isError);
  const notFound = probing && !finding && !found && !probeError;
  const tab = found ?? (probing ? visible[0] : resolved);
  const selected = queries[tab ?? "pending"];
  const retry = () => { visible.forEach(key => { void queries[key].refetch(); }); };
  return { tab, selected, finding, found, probeError, notFound, retry };
}

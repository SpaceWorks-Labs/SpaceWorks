import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getAccessToken, staffRequest, staffRequestBlob } from "../../lib/api";
import { browserSessionIdentity } from "../../lib/api/reauthentication";
import type { PlatformOverview, PlatformOverviewComputing } from "../../generated/api";

export type {
  OverviewBlock, OverviewCurrency, OverviewMetric, OverviewMoney, OverviewSpace, PlatformOverview,
} from "../../generated/api";

export type OverviewPreset = "this_month" | "this_year" | "all_time" | "custom";
export type OverviewQuery = { preset: OverviewPreset; start: string; end: string; includeExcluded: boolean };
export type OverviewResponse = PlatformOverview | PlatformOverviewComputing;

const BASE = "/admin/platform/overview";

/** A custom period is only sent once both dates are set; until then nothing is fetched. */
export function overviewReady(query: OverviewQuery) {
  return query.preset !== "custom" || Boolean(query.start && query.end && query.start <= query.end);
}

export function overviewParams(query: OverviewQuery) {
  const params = new URLSearchParams({ period: query.preset });
  if (query.preset === "custom") { params.set("start", query.start); params.set("end", query.end); }
  if (query.includeExcluded) params.set("include_excluded", "true");
  return params;
}

export function readyOverview(data: OverviewResponse | undefined): PlatformOverview | undefined {
  return data && data.status === "ready" ? data as PlatformOverview : undefined;
}

export function isComputing(data: OverviewResponse | undefined): data is PlatformOverviewComputing {
  return data?.status === "computing";
}

/**
 * Server state for the overview. The server answers 202 "computing" while Celery builds it,
 * so the query polls every few seconds until the cached result is ready, then stops.
 * The query key carries the session identity, so a different superadmin never sees a cached copy.
 */
export function usePlatformOverview(query: OverviewQuery) {
  return useQuery({
    queryKey: ["platform-overview", browserSessionIdentity(getAccessToken("platform")), overviewParams(query).toString()],
    enabled: overviewReady(query), retry: false, staleTime: 60_000, placeholderData: keepPreviousData,
    queryFn: () => staffRequest<OverviewResponse>(`${BASE}?${overviewParams(query)}`, {}, "platform"),
    refetchInterval: result => isComputing(result.state.data) ? result.state.data.retry_after_seconds * 1000 : false,
  });
}

/** Ask for a fresh computation; the next poll picks the result up. */
export function refreshOverview(query: OverviewQuery) {
  const params = overviewParams(query);
  params.set("refresh", "true");
  return staffRequest<OverviewResponse>(`${BASE}?${params}`, {}, "platform");
}

/** Downloads the CSV. Resolves false while the server is still computing (a JSON 202). */
export async function downloadOverviewCsv(query: OverviewQuery) {
  const blob = await staffRequestBlob(`${BASE}/export?${overviewParams(query)}`, { cache: "no-store" });
  if (blob.type.includes("json")) return false;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `platform-overview-${query.preset}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}

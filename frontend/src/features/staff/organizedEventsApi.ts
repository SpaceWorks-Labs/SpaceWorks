import { useQuery } from "@tanstack/react-query";

import type { ApiPath, EventListResponse } from "../../generated/api";
import { staffRequest } from "../../lib/api";

const ORGANIZED_EVENTS_PATH: ApiPath = "/api/v1/admin/organized-events/";

function staffPath(path: ApiPath) {
  return path.replace("/api/v1", "");
}

export type { EventAdmin, EventListResponse } from "../../generated/api";

export const organizedEventKeys = {
  all: ["events", "organized"] as const,
  list: (page: number, pageSize: number) =>
    [...organizedEventKeys.all, "list", page, pageSize] as const,
  every: () => [...organizedEventKeys.all, "every"] as const,
};

export function useOrganizedEvents(page: number, pageSize = 50) {
  return useQuery({
    queryKey: organizedEventKeys.list(page, pageSize),
    queryFn: () => staffRequest<EventListResponse>(
      `${staffPath(ORGANIZED_EVENTS_PATH)}?page=${page}&page_size=${pageSize}`,
    ),
  });
}

/** The endpoint has no status/date filter, so Upcoming and Past read every page (200 at a time) and filter whole. */
export function useEveryOrganizedEvent(enabled: boolean) {
  return useQuery({
    queryKey: organizedEventKeys.every(),
    enabled,
    queryFn: async () => {
      const results: EventListResponse["results"] = [];
      for (let page = 1; page <= 25; page += 1) { // cap: no server date filter yet; bounds a huge history
        const body = await staffRequest<EventListResponse>(`${staffPath(ORGANIZED_EVENTS_PATH)}?page=${page}&page_size=200`);
        results.push(...body.results);
        if (!body.next) break;
      }
      return { count: results.length, results };
    },
  });
}

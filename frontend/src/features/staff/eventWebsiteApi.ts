import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import type { EventWebsite, WebsiteTarget } from "../events/websiteTypes";
import { contentPayload } from "../events/websiteTypes";

export const websiteKey = (target: WebsiteTarget) => ["event-website", target.makerspaceId, target.kind, target.id] as const;
const base = (target: WebsiteTarget) => `/admin/${target.kind}/${target.id}/website/`;

export function useEventWebsite(target: WebsiteTarget, enabled = true) {
  return useQuery({ queryKey: websiteKey(target), enabled, staleTime: 0,
    queryFn: () => staffRequest<EventWebsite>(base(target)),
  });
}

export function useWebsiteInvalidation(target: WebsiteTarget) {
  const client = useQueryClient();
  return () => Promise.all([
    client.invalidateQueries({ queryKey: websiteKey(target) }),
    ...["public-event", "public-event-website", "public-events", "event", "events", "event-series", "event-discover"].map((key) => client.invalidateQueries({ queryKey: [key] })),
  ]);
}

export function useWebsiteSave(target: WebsiteTarget) {
  const invalidate = useWebsiteInvalidation(target);
  return useMutation({ mutationFn: (page: EventWebsite) => staffRequest<EventWebsite>(base(target), {
    method: "PUT", body: JSON.stringify(contentPayload(page)),
  }), onSuccess: invalidate });
}

export function useWebsiteRelease(target: WebsiteTarget) {
  const invalidate = useWebsiteInvalidation(target);
  return useMutation({ mutationFn: ({ released, revision }: { released: boolean; revision: number }) => staffRequest<EventWebsite>(`${base(target)}release/`, {
    method: "POST", body: JSON.stringify({ released, revision }),
  }), onSuccess: invalidate });
}

export function useWebsiteDelay(target: WebsiteTarget) {
  const invalidate = useWebsiteInvalidation(target);
  return useMutation({ mutationFn: ({ slug, minutes }: { slug: string; minutes: number }) => staffRequest<EventWebsite>(`${base(target)}sessions/${encodeURIComponent(slug)}/delay/`, {
    method: "POST", body: JSON.stringify({ delay_minutes: minutes }),
  }), onSuccess: invalidate });
}

export function useWebsiteAsset(target: WebsiteTarget) {
  const invalidate = useWebsiteInvalidation(target);
  return useMutation({ mutationFn: (data: FormData | number) => typeof data === "number"
    ? staffRequest<void>(`${base(target)}assets/${data}`, { method: "DELETE" })
    : staffRequest(`${base(target)}assets/`, { method: "POST", body: data }),
  onSuccess: invalidate });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { post, type Page } from "./parityRequest";

export type QueueKind = "archive-requests" | "api-key-requests" | "subdomain-requests";
export type QueueDecision = "approve" | "decline" | "reject";

export type ArchiveRequest = {
  id: number; makerspace: number; makerspace_name: string; status: "pending" | "approved" | "declined" | "withdrawn";
  reason: string; resolution_note: string; requested_at: string; resolved_at: string | null;
};
export type ApiKeyRequest = {
  id: number; makerspace: number; makerspace_name: string; label: string; reason: string; allowed_origins: string[];
  status: "pending" | "approved" | "rejected"; created_at: string; resolved_at: string | null;
};
export type IssuedClient = { request: ApiKeyRequest; client_id: string; client_secret: string };
export type SubdomainRequest = {
  id: number; makerspace: number; makerspace_name: string; requested_label: string;
  status: "pending" | "approved" | "rejected"; created_at: string; decided_at: string | null;
};

const queueKey = (kind: QueueKind) => ["platform-queue", kind] as const;

export function useQueue<T>(kind: QueueKind, status: string, page: number) {
  const params = new URLSearchParams({ page: String(page) });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: [...queueKey(kind), status, page],
    queryFn: () => staffRequest<Page<T>>(`/admin/platform/${kind}?${params}`, {}, "platform"),
  });
}

/**
 * One decision on one request. `gcTime: 0` drops the result as soon as the dialog closes, which
 * matters for an approved API key: its secret lives only in this mutation, never in a query cache.
 */
export function useQueueDecision<R>(kind: QueueKind, id: number, decision: QueueDecision) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, string>) => post<R>(`/admin/platform/${kind}/${id}/${decision}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: queueKey(kind) }),
    gcTime: 0,
  });
}

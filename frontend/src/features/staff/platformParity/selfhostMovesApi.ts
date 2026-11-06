import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { post, type Page } from "./parityRequest";

export type MoveStatus = "requested" | "approved" | "exporting" | "exported" | "rejected" | "failed" | "cancelled";
export type SelfhostMove = {
  id: string; makerspace: number; makerspace_name: string; status: MoveStatus; status_label: string; note: string;
  requested_at: string; decided_at: string | null; decision_note: string; recipient_fingerprint: string;
  exported_at: string | null; artifact_sha256: string; failure_code: string; has_file: boolean;
};
export type MoveAction = "approve" | "reject" | "export" | "discard";

export const MOVE_STATUS_LABELS: Record<MoveStatus, string> = {
  requested: t`Requested`, approved: t`Approved`, exporting: t`Exporting`, exported: t`Exported`,
  rejected: t`Declined`, failed: t`Failed`, cancelled: t`Cancelled`,
};

const BASE = "/admin/platform/selfhost-moves";
const key = ["platform-selfhost-moves"] as const;

/** Polls every five seconds only while an export on the page is still running. */
export function useSelfhostMoves(status: MoveStatus | "", page: number) {
  const params = new URLSearchParams({ page: String(page) });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: [...key, status, page],
    queryFn: () => staffRequest<Page<SelfhostMove>>(`${BASE}?${params}`, {}, "platform"),
    refetchInterval: query => query.state.data?.results.some(move => move.status === "exporting") ? 5000 : false,
  });
}

export function useMoveAction(id: string, action: MoveAction) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, string>) => post<SelfhostMove>(`${BASE}/${id}/${action}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}

/** A five-minute, one-use link; the browser follows it straight away so it is never shown or stored. */
export function useMoveDownload() {
  return useMutation({
    mutationFn: (id: string) => post<{ url: string; expires_at: string }>(`${BASE}/${id}/download-url`),
    onSuccess: link => window.location.assign(link.url),
  });
}

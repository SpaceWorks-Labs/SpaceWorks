import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { SessionContext } from "../../../lib/api/sessionContext";
import { refreshOrganizationAuthority } from "../refreshOrganizationAuthority";

// O-B5 routes; typed locally until the staging step regenerates `generated/api.ts`.
export type ReviewStatus = "pending_review" | "changes_requested" | "approved" | "declined" | "suspended";
export type ReviewDecision = "approve" | "decline" | "request_changes" | "suspend" | "reactivate";
export type ReviewAction = "submitted" | "changes_requested" | "approved" | "declined" | "suspended" | "reactivated";
export type ReviewEntry = { id: number; action: ReviewAction; reason: string; created_at: string };
export type ReviewQueueRow = {
  id: number; slug: string; name: string; description: string; website: string;
  review_status: ReviewStatus; created_at: string; submitted_by: string;
};
export type ReviewPage = { count: number; next: string | null; previous: string | null; results: ReviewQueueRow[] };

export const REVIEW_STATUSES: readonly ReviewStatus[] = ["pending_review", "changes_requested", "approved", "suspended", "declined"];

export const reviewStatusLabels = (): Record<ReviewStatus, string> => ({
  pending_review: t`Waiting for review`, changes_requested: t`Changes requested`, approved: t`Approved`,
  declined: t`Declined`, suspended: t`Suspended`,
});

export const reviewActionLabels = (): Record<ReviewAction, string> => ({
  submitted: t`Submitted for review`, changes_requested: t`Changes requested`, approved: t`Approved`,
  declined: t`Declined`, suspended: t`Suspended`, reactivated: t`Reactivated`,
});

export const reviewStatusTone = (status: ReviewStatus) =>
  status === "approved" ? "success" as const : status === "declined" || status === "suspended" ? "danger" as const : "warn" as const;

/** The decisions the server accepts from each standing (mirrors `services_review._DECISIONS`). */
export const DECISIONS_BY_STATUS: Record<ReviewStatus, readonly ReviewDecision[]> = {
  pending_review: ["approve", "request_changes", "decline"],
  changes_requested: ["approve", "decline"],
  approved: ["suspend"],
  suspended: ["reactivate"],
  declined: [],
};
/** The server refuses these without a reason. */
export const REASON_REQUIRED: ReadonlySet<ReviewDecision> = new Set(["decline", "request_changes", "suspend"]);

export const reviewKeys = {
  all: ["organization-reviews"] as const,
  queue: (status: ReviewStatus, page: number) => ["organization-reviews", "queue", status, page] as const,
  history: (id: number) => ["organization-reviews", "history", id] as const,
};

export function useReviewQueue(status: ReviewStatus, page: number) {
  return useQuery({
    queryKey: reviewKeys.queue(status, page),
    queryFn: () => staffRequest<ReviewPage>(`/admin/organization-reviews/?${new URLSearchParams({ status, page: String(page) })}`, {}, "platform"),
  });
}

/** Superadmins read from the platform console; the applicant's profile governors from their own session. */
export function useReviewHistory(id: number, enabled = true, context?: SessionContext) {
  return useQuery({
    queryKey: reviewKeys.history(id),
    queryFn: () => staffRequest<ReviewEntry[]>(`/admin/organizations/${id}/review/`, {}, context),
    enabled,
  });
}

export function useReviewDecision(id: number) {
  const client = useQueryClient();
  return useMutation({
    // A stale step-up answers `recent_reauth_required`; the API client prompts and retries once.
    mutationFn: (body: { decision: ReviewDecision; reason: string }) => staffRequest<{ id: number; review_status: ReviewStatus }>(
      `/admin/organizations/${id}/review/`, { method: "POST", body: JSON.stringify(body) }, "platform"),
    // Standing gates links, invitations and the public face, so every organization read refreshes.
    onSuccess: () => refreshOrganizationAuthority(client),
  });
}

export function useResubmitOrganization(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (note: string) => staffRequest<{ id: number; review_status: ReviewStatus }>(
      `/admin/organizations/${id}/resubmit/`, { method: "POST", body: JSON.stringify({ note }) }),
    onSuccess: () => refreshOrganizationAuthority(client),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { StructuredApiError } from "../../../lib/api/errors";
import { post, type Page } from "./spacesApi";

export type HostingRequestState = "submitted" | "changes_requested" | "accepted" | "rejected" | "pending_verification" | "invited" | "withdrawn";
export type HostingRequestRow = {
  id: number; status: HostingRequestState; source: string; space_name: string; proposed_slug: string; location: string;
  expected_members: number | null; applicant_name: string; applicant_email: string; applicant_phone: string;
  space_website_url: string; description: string; organization_choice: string; new_organization_name: string;
  inviter_summary: string; created_at: string; verified_at: string | null; decided_at: string | null; changes_note: string;
  created_makerspace: { id: number; name: string; slug: string } | null;
};
export type HostingRequestDetail = HostingRequestRow & {
  revisions: { kind: string; note: string; changed_fields: string[]; created_at: string }[];
};
export type ApproveBody = { name?: string; slug?: string; organization_id?: number; new_organization_name?: string; invite_manager: boolean };
export type ApproveResult = { request: HostingRequestRow; makerspace: { id: number; name: string; slug: string };
  invitation: "sent" | "skipped" | "unavailable" };

export const HOSTING_STATUS_LABELS: Record<HostingRequestState, string> = {
  submitted: "Submitted", changes_requested: "Changes requested", accepted: "Accepted", rejected: "Rejected",
  pending_verification: "Awaiting email check", invited: "Invited", withdrawn: "Withdrawn",
};

const BASE = "/admin/platform/hosting-requests";
const listKey = ["platform-hosting-requests"] as const;

/** 404 means a self-hosted deployment: the onboarding queue does not exist there. */
export function isSelfHost(error: unknown) {
  return error instanceof StructuredApiError && error.status === 404;
}

export function useHostingRequests(status: string, page: number) {
  return useQuery({
    queryKey: [...listKey, status, page],
    queryFn: () => staffRequest<Page<HostingRequestRow>>(`${BASE}?${new URLSearchParams({ ...(status ? { status } : {}), page: String(page) })}`, {}, "platform"),
    retry: false,
  });
}

export function useHostingRequest(id: number | null) {
  return useQuery({
    queryKey: [...listKey, "detail", id],
    queryFn: () => staffRequest<HostingRequestDetail>(`${BASE}/${id}`, {}, "platform"),
    enabled: id !== null,
  });
}

export function useHostingDecision<T>(id: number, action: "approve" | "request-changes" | "reject") {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: unknown) => post<T>(`${BASE}/${id}/${action}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: listKey }),
  });
}

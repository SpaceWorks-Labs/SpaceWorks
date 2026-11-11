import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { publicV1Request, staffRequest } from "../../lib/api";

import type * as Api from "../../generated/api";

// Wire types come from the generated OpenAPI client; these aliases keep the feature's names.
export type HostingAck = Api.HostingAck;
export type HostingRequestStatus = "invited" | "pending_verification" | "submitted" | "changes_requested" | "accepted" | "rejected" | "withdrawn";
/** `expected_members` (1..100000) is hand-added until the OpenAPI snapshot is regenerated. */
/** `location` is optional for an organization workspace (decision 295); typed locally until the snapshot is regenerated. */
export type HostingRequestBody = Omit<Api.HostingRequestSubmit, "location"> & { location?: string; expected_members?: number; requested_kind?: HostingKind };
/** Decision 295: a request asks for a makerspace (default) or an organization workspace. */
export type HostingKind = "makerspace" | "organization";
export type HostingInvitationSubmitBody = Omit<Api.HostingInvitationSubmit, "location"> & { location?: string; requested_kind?: HostingKind };
export type HostingRevision = { kind: "changes_requested" | "resubmitted"; note: string; changed_fields: string[]; created_at: string };
/** X31 adds the review note, history and the editable fields to the applicant's status read. */
export type HostingRequestDetails = Omit<Api.HostingRequestStatus, "status"> & { status: HostingRequestStatus; requested_kind?: HostingKind;
  changes_note?: string; revisions?: HostingRevision[]; editable?: boolean; location?: string;
  space_website_url?: string; description?: string };
export type HostingRequestView = HostingRequestDetails;
export type HostingResubmitBody = { space_name?: string; location?: string; space_website_url?: string; description?: string; note?: string };
export type HostingInvitationPreview = Api.HostingInvitationPreview;
export type HostingInvitation = Api.HostingInvitation;
export type HostingInvitationCreated = Api.HostingInvitationCreated;
export type HostingInvitationCreateBody = Api.HostingInvitationCreate;

type HostingConfig = { hosting_requests?: { enabled?: boolean; kinds?: string[] } };
const hostingConfigQuery = (enabled: boolean) => ({
  queryKey: ["public-config", "hosting"],
  queryFn: () => publicV1Request<HostingConfig>("/config"),
  enabled,
  staleTime: 5 * 60_000,
  retry: false,
});

/** `hosting_requests` is present in the public config only while the feature is available. */
export function useHostingConfig(enabled = true) {
  return useQuery({ ...hostingConfigQuery(enabled), select: (config: HostingConfig) => config.hosting_requests?.enabled === true });
}

/** The kinds the request form offers (decision 295); a config without `kinds` offers makerspaces only. */
export function useHostingKinds(enabled = true): HostingKind[] {
  const query = useQuery({ ...hostingConfigQuery(enabled), select: (config: HostingConfig) => config.hosting_requests?.kinds });
  const kinds = (query.data ?? []).filter((kind): kind is HostingKind => kind === "makerspace" || kind === "organization");
  return kinds.length ? kinds : ["makerspace"];
}

export function useHostingAvailability(enabled = true): boolean {
  return useHostingConfig(enabled).data === true;
}

function post<T>(path: string, body: unknown) {
  return publicV1Request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export function useSubmitHostingRequest() {
  return useMutation({ mutationFn: (body: HostingRequestBody) => post<HostingAck>("/public/hosting/requests", body) });
}

export function useOpenHostingRequest() {
  return useMutation({ mutationFn: (token: string) => post<HostingRequestView>("/public/hosting/requests/open", { token }) });
}

export function useResubmitHostingRequest() {
  return useMutation({ mutationFn: (body: HostingResubmitBody & { token: string }) => post<HostingRequestView>("/public/hosting/requests/resubmit", body) });
}

export function useResolveHostingInvitation() {
  return useMutation({
    mutationFn: (token: string) => post<HostingInvitationPreview>("/public/hosting/invitations/resolve", { token }),
  });
}

export function useSubmitHostingInvitation() {
  return useMutation({
    mutationFn: (body: HostingInvitationSubmitBody) => post<HostingAck>("/public/hosting/invitations/submit", body),
  });
}

export type HostingScope = { makerspaceId: number } | { organizationId: number };

/** Makerspace routes have no trailing slash; organization routes (DRF router) do. */
export function hostingInvitationsPath(scope: HostingScope) {
  return "makerspaceId" in scope
    ? `/admin/makerspaces/${scope.makerspaceId}/hosting-invitations`
    : `/admin/organizations/${scope.organizationId}/hosting-invitations/`;
}

export function hostingInvitationCancelPath(scope: HostingScope, id: number) {
  const base = hostingInvitationsPath(scope);
  return `${base}${base.endsWith("/") ? "" : "/"}${id}/cancel`;
}

function scopeKey(scope: HostingScope) {
  return "makerspaceId" in scope ? `makerspace-${scope.makerspaceId}` : `organization-${scope.organizationId}`;
}

export function useHostingInvitations(scope: HostingScope, page: number, enabled = true) {
  return useQuery({
    queryKey: ["hosting-invitations", scopeKey(scope), page],
    queryFn: () => staffRequest<Api.HostingInvitationPage>(`${hostingInvitationsPath(scope)}?page=${page}`),
    enabled,
  });
}

export function useCreateHostingInvitation(scope: HostingScope) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: HostingInvitationCreateBody) =>
      staffRequest<HostingInvitationCreated>(hostingInvitationsPath(scope), { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hosting-invitations", scopeKey(scope)] }),
  });
}

export function useCancelHostingInvitation(scope: HostingScope) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => staffRequest<HostingInvitation>(hostingInvitationCancelPath(scope, id), { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hosting-invitations", scopeKey(scope)] }),
  });
}

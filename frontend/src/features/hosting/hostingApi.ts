import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { publicV1Request, staffRequest } from "../../lib/api";

import type * as Api from "../../generated/api";

// Wire types come from the generated OpenAPI client; these aliases keep the feature's names.
export type HostingAck = Api.HostingAck;
export type HostingRequestStatus = Api.StatusAc9Enum;
export type HostingRequestBody = Api.HostingRequestSubmit;
export type HostingInvitationSubmitBody = Api.HostingInvitationSubmit;
export type HostingRequestView = Api.HostingRequestStatus;
export type HostingInvitationPreview = Api.HostingInvitationPreview;
export type HostingInvitation = Api.HostingInvitation;
export type HostingInvitationCreated = Api.HostingInvitationCreated;
export type HostingInvitationCreateBody = Api.HostingInvitationCreate;

/** `hosting_requests` is present in the public config only while the feature is available. */
export function useHostingConfig(enabled = true) {
  return useQuery({
    queryKey: ["public-config", "hosting"],
    queryFn: () => publicV1Request<{ hosting_requests?: { enabled?: boolean } }>("/config"),
    select: (config) => config.hosting_requests?.enabled === true,
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
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

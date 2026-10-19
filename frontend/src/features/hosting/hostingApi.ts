import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { publicV1Request, staffRequest } from "../../lib/api";

// Hand-written until the OpenAPI snapshot carries the hosting routes.

export type HostingAck = { detail: string };
export type HostingRequestStatus = "invited" | "pending_verification" | "submitted" | "accepted" | "rejected" | "withdrawn";

export type HostingRequestBody = {
  applicant_name: string;
  applicant_email: string;
  applicant_phone?: string;
  space_name: string;
  location: string;
  space_website_url?: string;
  description: string;
  proposed_slug?: string;
  new_organization_name?: string;
  /** Honeypot: always sent, normally empty. */
  website: string;
};
export type HostingInvitationSubmitBody = HostingRequestBody & { token: string; organization_choice: "own" | "join" };

export type HostingRequestView = {
  status: HostingRequestStatus;
  space_name: string;
  created_at: string;
  verified_at: string | null;
  decided_at: string | null;
  rejection_reason: string | null;
};

export type HostingInvitationPreview = {
  inviter_name: string;
  join_organization_name: string | null;
  space_name: string;
  applicant_email: string;
  invite_note: string;
  expires_at: string;
};

export type HostingInvitation = {
  id: number;
  space_name: string;
  status: HostingRequestStatus;
  display_status: HostingRequestStatus | "expired";
  join_offered: boolean;
  created_at: string;
  invite_expires_at: string;
};
export type HostingInvitationCreated = HostingInvitation & { invite_url: string; delivery_status: string };
export type HostingInvitationCreateBody = { invitee_email: string; space_name?: string; note?: string };
export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

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
    queryFn: () => staffRequest<Paginated<HostingInvitation>>(`${hostingInvitationsPath(scope)}?page=${page}`),
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

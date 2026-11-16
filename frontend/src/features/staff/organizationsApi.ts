import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { publicOrganizationKeys } from "../organizations/publicOrganizationsApi";
import { refreshOrganizationAuthority } from "../organizations/refreshOrganizationAuthority";

export type Page<T> = import("../publicPages/pageTypes").Collection<T>;
export type OrganizationSummary = import("../../generated/api").OrganizationSummary;
type ApiDetail = import("../../generated/api").OrganizationDetail;
type SensitiveFields = "legal_name" | "registration_number" | "contact_email" | "billing_email";
// The serializer omits these fields for readers without profile-governance authority.
export type OrganizationDetail = Omit<ApiDetail, SensitiveFields> & Partial<Pick<ApiDetail, SensitiveFields>>;
type Actions = { governance_actions: string[]; granted_actions: string[] };
// These two model JSON fields are validated action lists; OpenAPI currently emits unknown.
export type OrganizationMember = Omit<import("../../generated/api").OrganizationMembership, keyof Actions> & Actions;
export type OrganizationInvitation = Omit<import("../../generated/api").OrganizationInvitation, keyof Actions> & Actions;
export type CreatedInvitation = Omit<import("../../generated/api").OrganizationInvitationCreated, keyof Actions> & Actions;
export type OrganizationLink = import("../../generated/api").OrganizationLink;

export function useOrganizationLinks(id: number, enabled: boolean, page = 1) {
  return useQuery({ queryKey: ["organizations", id, "links", page], enabled,
    queryFn: () => staffRequest<Page<OrganizationLink>>(`/admin/organizations/${id}/makerspaces/?page=${page}`) });
}
export function useCreateOrganization() {
  const client = useQueryClient();
  return useMutation({ mutationFn: (payload: { name: string; slug: string }) => staffRequest<OrganizationDetail>("/admin/organizations/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => client.invalidateQueries({ queryKey: organizationKeys.all }) });
}
export function useChangeOrganizationLink(id: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ makerspace_id, relationship }: { makerspace_id: number; relationship?: OrganizationLink["relationship"] }) =>
    staffRequest(`/admin/organizations/${id}/makerspaces/${relationship ? "" : `${makerspace_id}/`}`, { method: relationship ? "POST" : "DELETE", ...(relationship ? { body: JSON.stringify({ makerspace_id, relationship }) } : {}) }),
    onSuccess: () => refreshOrganizationAuthority(client) });
}

type OrganizationFilters = { page?: number; search?: string; active?: boolean };

export const organizationKeys = {
  all: ["organizations"] as const,
  list: (filters: number | OrganizationFilters = {}) => {
    const { page = 1, search = "", active }: OrganizationFilters = typeof filters === "number" ? { page: filters } : filters;
    return ["organizations", "list", { page, search, active }] as const;
  },
  detail: (id: number) => ["organizations", id] as const,
  memberships: (id: number, page: number) => ["organizations", id, "memberships", page] as const,
  invitations: (id: number, page: number) => ["organizations", id, "invitations", page] as const,
};

export function useOrganizations(filters: number | OrganizationFilters = {}) {
  const { page = 1, search = "", active }: OrganizationFilters = typeof filters === "number" ? { page: filters } : filters;
  const params = new URLSearchParams({ page: String(page), search });
  if (active !== undefined) params.set("active", String(active));
  return useQuery({
    queryKey: organizationKeys.list({ page, search, active }),
    queryFn: () => staffRequest<Page<OrganizationSummary>>(`/admin/organizations/?${params}`),
  });
}

export function useOrganization(id: number | null) {
  return useQuery({
    queryKey: organizationKeys.detail(id ?? 0),
    queryFn: () => staffRequest<OrganizationDetail>(`/admin/organizations/${id}/`),
    enabled: id !== null,
  });
}

export function useOrganizationMemberships(id: number, page: number, enabled: boolean) {
  return useQuery({
    queryKey: organizationKeys.memberships(id, page),
    queryFn: () => staffRequest<Page<OrganizationMember>>(`/admin/organizations/${id}/memberships/?page=${page}`),
    enabled,
  });
}

export function useOrganizationInvitations(id: number, page: number, enabled: boolean) {
  return useQuery({
    queryKey: organizationKeys.invitations(id, page),
    queryFn: () => staffRequest<Page<OrganizationInvitation>>(`/admin/organizations/${id}/invitations/?page=${page}`),
    enabled,
  });
}

export function useUpdateOrganization(id: number, slug: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Pick<OrganizationDetail, "name" | "slug" | "description" | "website" | "public_profile_enabled" | "is_discoverable">>) =>
      staffRequest<OrganizationDetail>(`/admin/organizations/${id}/`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: async (updated) => Promise.all([
      client.invalidateQueries({ queryKey: organizationKeys.all }),
      client.invalidateQueries({ queryKey: organizationKeys.detail(id) }),
      client.invalidateQueries({ queryKey: publicOrganizationKeys.root(slug) }),
      client.invalidateQueries({ queryKey: publicOrganizationKeys.root(updated.slug) }),
    ]),
  });
}

export function useCreateOrganizationInvitation(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: { governance_actions: string[]; granted_actions: string[]; expires_in_days: number; invitee_email?: string }) =>
      staffRequest<CreatedInvitation>(`/admin/organizations/${id}/invitations/`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["organizations", id, "invitations"] }),
  });
}

export function useRevokeOrganizationInvitation(organizationId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: number) => staffRequest<void>(`/admin/organization-invitations/${invitationId}/`, { method: "DELETE" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["organizations", organizationId, "invitations"] }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest, getAccessToken } from "../../lib/api";
import { browserSessionIdentity } from "../../lib/api/reauthentication";
import type { OrganizationDetail, OrganizationMember } from "../staff/organizationsApi";
import { refreshOrganizationAuthority } from "./refreshOrganizationAuthority";

export const organizationSelfServiceKey = ["organizations", "self-service"] as const;
export type OrganizationCreationPolicy = {
  enabled: boolean; eligible: boolean; max_owned: number; max_per_day: number; reason: string;
};

/** `enabled` lets a caller share this cache entry without fetching where self-service cannot exist. */
export function useOrganizationCreationPolicy(enabled = true) {
  return useQuery({ queryKey: [...organizationSelfServiceKey, browserSessionIdentity(getAccessToken())],
    queryFn: () => staffRequest<OrganizationCreationPolicy>("/auth/organizations/self-service/"), enabled });
}

export function useCreateOwnOrganization() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; slug: string }) => staffRequest<OrganizationDetail>(
      "/auth/organizations/self-service/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => refreshOrganizationAuthority(client),
  });
}

export function useDeleteOrganization(id: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: () => staffRequest<void>(`/admin/organizations/${id}/`, { method: "DELETE" }),
    onSuccess: () => refreshOrganizationAuthority(client) });
}

export function useUpdateOrganizationMember(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, ...payload }: { memberId: number; status?: "active" | "suspended"; governance_actions?: string[]; granted_actions?: string[] }) =>
      staffRequest<OrganizationMember>(`/admin/organizations/${id}/memberships/${memberId}/`, {
        method: "PATCH", body: JSON.stringify(payload),
      }),
    onSuccess: () => refreshOrganizationAuthority(client),
  });
}

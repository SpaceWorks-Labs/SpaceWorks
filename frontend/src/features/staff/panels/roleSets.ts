import type { QueryClient } from "@tanstack/react-query";
import type { StaffRole } from "./rolesApi";

export type MembershipRoles = {
  role_ids: number[];
  roles: Pick<StaffRole, "id" | "slug" | "name">[];
};

export function assignableRoles(roles: StaffRole[], actions: readonly string[], isSuperadmin: boolean) {
  if (isSuperadmin) return roles;
  const ceiling = new Set(actions.filter((action) => action !== "manage_makerspace"));
  return roles.filter((role) => !role.granted_actions.includes("manage_makerspace")
    && role.granted_actions.every((action) => ceiling.has(action)));
}

export function refreshMembershipAuthority(client: QueryClient, msId: number) {
  return Promise.all([
    ["staff", "memberships", msId], ["staff", "roles", msId],
    ["members", msId], ["member-machine-scope", msId], ["staff", "me"],
  ].map((queryKey) => client.invalidateQueries({ queryKey })));
}

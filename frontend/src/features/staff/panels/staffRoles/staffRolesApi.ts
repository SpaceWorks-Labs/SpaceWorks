import { staffRequest } from "../../../../lib/api";
import { StructuredApiError } from "../../../../lib/api/errors";
import type { StaffRole } from "../rolesApi";

/** A staff row is a role set on a person's own account, never a separate account. */
export type StaffRoleRow = {
  id: number; user_id: number; username: string; display_name: string; email: string;
  roles: string[]; machine_type_ids: number[]; status: "active" | "revoked"; mfa_enabled: boolean;
  granted_at: string; revoked_at: string | null; revocation_reason: string;
  can: { change_roles: boolean; revoke: boolean; restore: boolean; reset_mfa: boolean };
  pii_masked?: boolean;
};
export type GrantableRole = { slug: string; name: string; combinable: boolean };
export type StaffRolesPolicy = {
  grantable_roles: GrantableRole[]; can_manage_space_managers: boolean;
  email_invites_available: boolean; machine_types: { id: number; name: string }[];
};
export type StaffRolesPage = { count: number; next: string | null; previous: string | null; results: StaffRoleRow[]; policy: StaffRolesPolicy };
export type GrantBody = { roles: string[]; machine_type_ids: number[] } & ({ user_id: number } | { email: string; expires_in_days?: number });
export type GrantResult = { kind: "granted" | "invited"; staff_role: StaffRoleRow | null; invitation_id: number | null; delivery_status: string | null };
export type StaffInvitation = {
  id: number; email: string; role_name: string; roles: string[]; machine_type_ids: number[];
  expires_at: string; accepted_at: string | null; revoked_at: string | null; created_at: string; pii_masked?: boolean;
};
export type InvitationsPage = { count: number; next: string | null; previous: string | null; results: StaffInvitation[] };

export const staffRolesKey = (space: number) => ["staff-roles", space] as const;
export const invitationsKey = (space: number) => ["staff", "invitations", space] as const;
export const spaceRolesKey = (space: number) => ["staff", "roles", space] as const;

const base = (space: number) => `/admin/makerspaces/${space}/staff-roles/`;
const invitations = (space: number) => `/admin/makerspaces/${space}/staff-invitations`;
const post = <T>(path: string, body: object = {}) => staffRequest<T>(path, { method: "POST", body: JSON.stringify(body) });

export const listStaffRoles = (space: number, page: number, includeRevoked: boolean) =>
  staffRequest<StaffRolesPage>(`${base(space)}?page=${page}&include_revoked=${includeRevoked ? 1 : 0}`);
export const grantStaffRole = (space: number, body: GrantBody) => post<GrantResult>(base(space), body);
export const changeStaffRole = (space: number, id: number, body: { roles?: string[]; machine_type_ids?: number[] }) =>
  staffRequest<StaffRoleRow>(`${base(space)}${id}/`, { method: "PATCH", body: JSON.stringify(body) });
export const revokeStaffRole = (space: number, id: number, reason: string) => post<StaffRoleRow>(`${base(space)}${id}/revoke/`, { reason });
export const restoreStaffRole = (space: number, id: number) => post<StaffRoleRow>(`${base(space)}${id}/restore/`);
export const resetStaffMfa = (space: number, id: number, reason: string) =>
  post<{ reset: true; rule: string }>(`${base(space)}${id}/mfa-reset`, { reason });
export const listStaffInvitations = (space: number, page: number) => staffRequest<InvitationsPage>(`${invitations(space)}?page=${page}`);
export const resendStaffInvitation = (space: number, id: number) =>
  post<StaffInvitation & { delivery_status: string }>(`${invitations(space)}/${id}/resend`);
export const revokeStaffInvitation = (space: number, id: number) => post<StaffInvitation>(`${invitations(space)}/${id}/revoke`);
export const listSpaceRoles = (space: number) => staffRequest<StaffRole[]>(`/admin/makerspaces/${space}/roles`);

const ERROR_COPY: Record<string, string> = {
  last_manager: "A makerspace keeps at least one active Space Manager.",
  self_change: "You can't change your own staff roles.",
  not_community_member: "Only community members of this space can be granted a role here. Invite them by email instead.",
  already_staff: "This person already has a staff row here. Change or restore it.",
  quota_exceeded: "This makerspace has reached its staff limit.",
  tenant_gated: "This makerspace is temporarily read-only.",
  space_manager_superadmin_only: "Only the platform administrator manages Space Managers.",
  mfa_reset_not_allowed: "You can't reset this person's authenticator. Ask the platform administrator.",
};

/** Friendly copy for the refusal codes the staff-roles API returns; the server message otherwise. */
export function staffRoleErrorText(error: unknown) {
  if (error instanceof StructuredApiError && error.code && ERROR_COPY[error.code]) return ERROR_COPY[error.code];
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}

export const deliveryText = (status: string | null | undefined) => status === "sent"
  ? "Invitation email sent." : "The email could not be sent; ask them to check the address and resend.";

const humanize = (slug: string) => slug.split("_").map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
export const roleNames = (policy: StaffRolesPolicy | undefined, slugs: string[]) =>
  slugs.map(slug => policy?.grantable_roles.find(role => role.slug === slug)?.name ?? humanize(slug)).join(" + ");

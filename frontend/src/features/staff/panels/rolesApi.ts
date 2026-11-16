import { staffRequest } from "../../../lib/api";

export type StaffRole = {
  id: number;
  makerspace_id: number;
  name: string;
  slug: string;
  granted_actions: string[];
  legacy_role: string | null;
  is_default: boolean;
  is_protected: boolean;
  combinable: boolean;
  exclusive: boolean;
  member_count: number;
  created_at: string;
  updated_at: string;
};

export type StaffMembershipRow = {
  id: number;
  user: { id: number; username: string; email: string; access_status: string };
  makerspace_id: number;
  makerspace_slug: string;
  role: string;
  role_ids: number[];
  roles: Pick<StaffRole, "id" | "name" | "slug">[];
  status: "active" | "revoked";
  assigned_role: Pick<StaffRole, "id" | "name" | "slug" | "legacy_role" | "is_default" | "is_protected"> | null;
  created_at: string;
};

export type MemberMachineScope = {
  membership_id: number;
  scoping_applies: boolean;
  machine_type_ids: number[];
  available_machine_types: { id: number; name: string; slug: string; is_global: boolean }[];
  /** Decision 282: single machines alongside whole types (union); absent on an older server. */
  machine_ids?: number[];
  available_machines?: { id: number; name: string; machine_type_id: number }[];
};

export function getMemberMachineScope(msId: number, membershipId: number) {
  return staffRequest<MemberMachineScope>(`/admin/makerspaces/${msId}/memberships/${membershipId}/machine-scope`);
}

export function setMemberMachineScope(msId: number, membershipId: number, machineTypeIds: number[], machineIds?: number[]) {
  return staffRequest<MemberMachineScope>(`/admin/makerspaces/${msId}/memberships/${membershipId}/machine-scope`, {
    method: "PUT", body: JSON.stringify({ machine_type_ids: machineTypeIds, ...(machineIds ? { machine_ids: machineIds } : {}) }),
  });
}

export function createMembership(msId: number, body: {
  username: string; email?: string; first_name?: string; last_name?: string; password?: string; role_ids: number[];
}) {
  return staffRequest<StaffMembershipRow>(`/admin/makerspaces/${msId}/memberships`, { method: "POST", body: JSON.stringify(body) });
}

export function assignRole(msId: number, membershipId: number, roleIds: number[]) {
  return staffRequest<StaffMembershipRow>(`/admin/makerspaces/${msId}/memberships/${membershipId}/role`, {
    method: "PATCH", body: JSON.stringify({ role_ids: roleIds }),
  });
}

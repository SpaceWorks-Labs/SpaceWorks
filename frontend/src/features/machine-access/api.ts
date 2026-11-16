import { memberRequest, staffRequest } from "../../lib/api";

/** Decision 319: machine use is granted by the space manager, per machine or per machine type. */
export type AccessStatus = "live" | "expired" | "revoked";
export type MachineAccessGrant = {
  id: number; member: number; member_name: string;
  machine: number | null; machine_name: string | null;
  machine_type: number | null; machine_type_name: string | null;
  granted_by_name: string; granted_at: string; expires_at: string | null;
  note: string; source: "staff" | "migration"; revoked_at: string | null; status: AccessStatus;
};
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type AccessFilters = { machineId?: number; machineTypeId?: number; memberId?: number; status?: AccessStatus | "all"; source?: "migration"; page?: number };
export type GrantInput = { member_ids?: number[]; membership_ids?: number[]; machine_id?: number | null; machine_type_id?: number | null; expires_at?: string | null; note?: string };
export type GrantResult = { granted: MachineAccessGrant[]; failed: { member_id: number; detail: string }[] };
export type Candidate = { user_id: number; name: string };

export const accessKeys = {
  all: (space: number) => ["machine-access", space] as const,
  list: (space: number, filters: AccessFilters) => ["machine-access", space, "list", filters] as const,
  candidates: (space: number, q: string) => ["machine-access", space, "candidates", q] as const,
  mine: (space: number) => ["member", space, "machine-access"] as const,
};

export function listAccess(space: number, filters: AccessFilters) {
  const params = new URLSearchParams({ status: filters.status ?? "live", page: String(filters.page ?? 1) });
  if (filters.machineId) params.set("machine_id", String(filters.machineId));
  if (filters.machineTypeId) params.set("machine_type_id", String(filters.machineTypeId));
  if (filters.memberId) params.set("member_id", String(filters.memberId));
  if (filters.source) params.set("source", filters.source);
  return staffRequest<Page<MachineAccessGrant>>(`/admin/makerspaces/${space}/machine-access?${params}`);
}
export const grantAccess = (space: number, input: GrantInput) =>
  staffRequest<GrantResult>(`/admin/makerspaces/${space}/machine-access`, { method: "POST", body: JSON.stringify(input) });
export const revokeAccess = (id: number) =>
  staffRequest<MachineAccessGrant>(`/admin/machine-access/${id}/revoke`, { method: "POST" });
export const findCandidates = (space: number, q: string) =>
  staffRequest<{ results: Candidate[] }>(`/admin/makerspaces/${space}/machine-access/candidates?q=${encodeURIComponent(q)}`);
export const setOpenToAll = (machineId: number, open: boolean) =>
  staffRequest<{ open_to_all_members: boolean }>(`/admin/machines/${machineId}/open-access`, { method: "PATCH", body: JSON.stringify({ open_to_all_members: open }) });

export type MyGrant = { id: number; machine_id: number | null; machine_name: string | null; machine_type_name: string | null;
  granted_at: string; expires_at: string | null; status: "live" | "expired" };
export type MyMachineAccess = { grants: MyGrant[]; open_machines: { id: number; name: string }[] };
export const getMyAccess = (space: number) => memberRequest<MyMachineAccess>(`/member/makerspaces/${space}/machine-access`);

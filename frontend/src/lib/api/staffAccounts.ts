import { staffRequest } from "./requests";
import type { StaffRole } from "../../features/staff/panels/rolesApi";

export const STAFF_ROLE_NAMES = {
  space_manager: "Space Manager", inventory_manager: "Inventory Manager", machine_manager: "Machine Manager",
  event_manager: "Event Manager", booking_manager: "Booking Manager", handover: "Handover", technician: "Technician",
} as const;
export type StaffRoleKey = keyof typeof STAFF_ROLE_NAMES;
export type StaffAccount = {
  id: number; username: string; display_name: string; email: string; roles: StaffRoleKey[];
  machine_type_ids: number[]; is_active: boolean; must_change_password: boolean; mfa_enabled: boolean;
  last_login: string | null; created_at: string; invitation_pending: boolean;
  can: Record<"change_roles" | "set_password" | "deactivate" | "reactivate" | "resend_invite", boolean>;
};
export type StaffAccountPolicy = {
  creatable_roles: StaffRoleKey[]; can_manage_space_managers: boolean;
  email_onboarding_available: boolean;
  machine_types: { id: number; name: string }[];
  roles: StaffRole[];
};
export type StaffAccountDraft = {
  display_name: string; email?: string; username?: string; roles: StaffRoleKey[]; machine_type_ids: number[];
};
export type StaffAccountsPage = { count: number; next: string | null; previous: string | null; results: StaffAccount[] };
const base = (space: number) => `/admin/makerspaces/${space}/staff-accounts/`;
const post = <T>(path: string, body = {}) => staffRequest<T>(path, { method: "POST", body: JSON.stringify(body) });
export const listStaffAccounts = (space: number, page: number, inactive: boolean) =>
  staffRequest<StaffAccountsPage>(`${base(space)}?page=${page}${inactive ? "&include_inactive=1" : ""}`);
export const staffAccountPolicy = (space: number) => staffRequest<StaffAccountPolicy>(`${base(space)}policy`);
export const createStaffAccount = (space: number, draft: StaffAccountDraft) =>
  post<{ account: StaffAccount; invitation_sent: boolean }>(base(space), draft);
export const updateStaffAccount = (space: number, user: number, draft: Pick<StaffAccountDraft, "roles" | "machine_type_ids">) =>
  staffRequest<StaffAccount>(`${base(space)}${user}/`, { method: "PATCH", body: JSON.stringify(draft) });
export const deactivateStaffAccount = (space: number, user: number, reason: string) =>
  post<StaffAccount>(`${base(space)}${user}/deactivate/`, { reason });
export const reactivateStaffAccount = (space: number, user: number) => post<StaffAccount>(`${base(space)}${user}/reactivate/`);
export const resendStaffInvite = (space: number, user: number) =>
  post<{ invitation_sent: boolean }>(`${base(space)}${user}/resend-invite/`);
export const setStaffPassword = (space: number, user: number, body: { password?: string; generate?: true; reset_mfa: boolean }) =>
  post<{ generated_password: string | null }>(`${base(space)}${user}/set-password/`, body);

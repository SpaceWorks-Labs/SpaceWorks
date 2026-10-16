export type StaffForm = {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  role_ids: number[];
  makerspace_id: string;
};
export type RestrictForm = { status: "restricted" | "suspended"; reason: string };
export type MakerspaceForm = {
  profile?: Partial<{ timezone: string; country: string; default_currency: string; opening_hours: import("../../makerspaceProfileForm").OpeningHours }>;
  modules?: string[];
  first_staff_email?: string;
  first_staff_role?: "space_manager" | "inventory_manager" | "machine_manager" | "event_manager" | "booking_manager" | "handover";
  install_profile_id?: number | "";
  name: string;
  public_code: string;
  slug: string;
  location: string;
  superadmin_access_enabled: boolean;
};
export type ResetPasswordForm = { password: string };
export type ResetPasswordResult = { username: string; temporary_password: string };

export type TenantBootstrap = {
  makerspace: {
    id: number;
    name: string;
    slug: string;
    public_code: string;
    location: string;
    timezone?: string;
    opening_hours?: import("../../features/staff/makerspaceProfileForm").OpeningHours;
    map_url?: string;
    logo_url?: string | null;
    cover_image_url?: string | null;
    geofence_enabled: boolean;
    public_stats_enabled?: boolean;
    public_site_enabled?: boolean;
    public_inventory_enabled?: boolean;
    public_landing_page?: "auto" | "inventory" | "events" | "machines" | "bookings" | "membership";
    membership_policy: "request" | "open" | "invite_only";
    // Present only for a makerspace without member accounts (#80): borrow requests then
    // take name, phone, email and an email code instead of a signed-in account.
    request_access?: "contact";
  };
  frontend: {
    type: string;
    hostname: string;
    allowed_origins: string[];
  };
  modules: string[];
  features: string[];
  workflows: string[];
  // Deployment edition (phase 4): `makerspace` (default), `events`, `bookings`, `organization`.
  // Absent on backends that predate it. Module keys the edition hides are already removed
  // from `modules`, so route gating needs nothing beyond that list.
  edition?: string;
  theme: Record<string, string>;
  branding: Record<string, string>;
  email_enabled: boolean;
  public_api: {
    base_url: string;
    publishable_key: string;
    inventory_path: string;
  };
};

export type StaffAuthUser = {
  account_kind?: "member" | "staff" | "platform";
  staff_makerspace?: { id: number; slug: string; name: string } | null;
  username: string;
  email_verified: boolean;
  role: string;
  is_superuser: boolean;
  must_change_password: boolean;
  /** Every action the platform superadmin holds in each servable space (#115); [] otherwise. */
  superadmin_actions?: string[];
  booking_grants?: {
    space_id: number; makerspace_id: number; makerspace_slug: string;
    name: string; source: "booking_grant"; permissions: string[];
  }[];
  event_grants?: {
    event_id: number | null; series_id: number | null; makerspace_id: number;
    makerspace_slug: string; title: string; source: "event_grant"; permissions: string[];
  }[];
  makerspaces: {
    id: number;
    slug: string;
    role: string | null;
    role_id: number | null;
    role_ids: number[];
    role_slugs: string[];
    role_names: string[];
    role_name: string;
    role_slug: string | null;
    source: "membership" | "organization";
    actions: string[];
    can_configure_machine_types: boolean;
    is_machine_only: boolean;
    can_refer: boolean;
    can_verify: boolean;
    verified_at: string | null;
    referrals_enabled: boolean;
  }[];
};

export type PasswordLoginRequestedSurface = "member" | "staff" | "delegated";
export type PasswordLoginSurface = PasswordLoginRequestedSurface | "verification_only";
export type PasswordLoginRequest = {
  username: string;
  password: string;
  surface: PasswordLoginRequestedSurface;
  context?: "member" | "staff" | "platform";
  makerspace?: string;
};
export type PasswordLoginResponse<TUser = unknown> = {
  access: string;
  surface: PasswordLoginSurface;
  user: TUser;
};

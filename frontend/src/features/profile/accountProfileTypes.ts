/** Hand-typed from PROFILE-CONTRACT-0.12.0 (AccountProfileSerializer). One global profile per account. */
export type ProfileSkill = { name: string; level: number };
export type ProfileLink = { kind: string; url: string };
export type TimelineKind = "experience" | "education" | "volunteering";
export type Audience = "owner" | "member" | "public";
export type StatusPreset = "student" | "working" | "freelancing" | "looking_for_work" | "open_to_collaborate" | "building_startup" | "other" | "";

/** `shown` keys are the toggle names without the `show_` prefix. */
export const SECTION_KEYS = ["status", "about", "experience", "education", "achievements", "projects", "skills", "links", "interests", "events", "spaces", "certifications"] as const;
export type SectionKey = typeof SECTION_KEYS[number];
export type Shown = Record<SectionKey, boolean>;

/** Row ids are owner-only: other audiences get rows without them. */
export type TimelineRow = {
  id?: number; kind: TimelineKind; title: string; organization: string; location: string;
  start: string; end: string | null; description: string; order: number;
};
export type ProfileProject = {
  id?: number; title: string; subtitle: string; tags: string[]; public_visible: boolean; description: string;
  links: { label: string; url: string }[]; image_url: string | null; imported: boolean;
};
export type VerifiedKind = "award" | "peoples_choice" | "role" | "speaker" | "attended";
export type VerifiedAchievement = {
  kind: VerifiedKind; event_title?: string; verified_by: string; occurred_on?: string; rank?: number | null;
  prize_name?: string; role?: string; count?: number;
};
export type SelfReportedAchievement = {
  id?: number; title: string; issuer: string; achieved_on: string | null; url: string; description: string; order: number;
};
export type SpaceRow = { slug: string; name: string; kind: "makerspace" | "organization"; role_title: string | null };
export type OrganizationRow = { slug: string; name: string; source: "explicit" | "derived" };

export type AccountProfile = {
  audience: Audience;
  handle: string | null; /** null for logged-out readers. */ account_id: number | null; display_name: string; avatar_url: string | null;
  headline: string; institution: string;
  shown: Shown;
  status: { preset: StatusPreset; note: string } | null;
  bio: string;
  timeline: TimelineRow[];
  education: { institution: string; qualification?: string; year?: string }[];
  skills: ProfileSkill[]; domains: string[]; links: ProfileLink[]; interests: string[]; languages: string[];
  projects: ProfileProject[];
  achievements: { verified: VerifiedAchievement[]; self_reported: SelfReportedAchievement[] };
  events_attended: { count: number; recent: { id: number; title: string; starts_at: string; space_name: string }[] } | null;
  certifications: { name: string; space_name: string }[];
  spaces: SpaceRow[]; organizations: OrganizationRow[];
  /** Part of the `spaces` section. A voucher is named only when readable; everyone else is only counted. */
  vouched_by?: { handle: string; display_name: string; space_name: string }[]; vouched_count?: number;
  /** Which activity-graph families are switched on. */
  activity_shown?: Record<ActivityFamily, boolean>;
  github_username?: string; github_contributions?: number | null;
  /** Decision 338: true only when the username matches the owner's linked GitHub sign-in; gates the badge and calendar. */
  github_verified?: boolean;
  /** Owner only. */
  is_visible?: boolean; public_visible?: boolean; public_consented_at?: string | null;
  /** Owner only (decision 335c): profiles were merged, so open-web publishing waits for a fresh confirmation. */
  public_reconfirm_pending?: boolean;
  toggles?: { is_visible: boolean } & Record<`show_${SectionKey}`, boolean> & Partial<Record<`show_${ActivityFamily}`, boolean>>;
};

export const ACTIVITY_FAMILIES = ["activity_graph", "speaking", "machine_activity", "bookings", "loans"] as const;
export type ActivityFamily = typeof ACTIVITY_FAMILIES[number];

/** Body of PATCH /member/profile: any subset. */
export type ProfilePatch = Partial<{
  is_visible: boolean; public_visible: boolean; publication_consent: boolean;
  headline: string; status: StatusPreset; status_note: string; institution: string; bio: string;
  domains: string[]; skills: ProfileSkill[]; links: ProfileLink[]; interests: string[]; languages: string[];
  projects: { id?: number; title: string; subtitle: string; tags: string[]; public_visible: boolean; description: string; links: { label: string; url: string }[] }[];
  github_username: string;
}> & Partial<Record<`show_${SectionKey}` | `show_${ActivityFamily}`, boolean>>;

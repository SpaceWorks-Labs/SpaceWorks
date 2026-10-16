import type { FamilyFlags, ProfileLink, ProfileSkill } from "../../profile/publicProfileApi";

export type MemberProject = {
  id: number;
  title: string;
  subtitle?: string;
  tags?: string[];
  public_visible?: boolean;
  description: string;
  links: { label: string; url: string }[];
  image_url: string | null;
};

export interface MemberProfileActivity {
  events_attended?: number;
  events_registered?: number;
  recent_attended_events?: { id: number; title: string; starts_at: string }[];
}

/** Public-page publication fields from the Phase 1b contract. Optional so older payloads still type-check. */
export type MemberPublication = Partial<FamilyFlags> & {
  handle?: string | null;
  public_visible?: boolean;
  public_consented_at?: string | null;
  domains?: string[];
  skills?: ProfileSkill[];
  links?: ProfileLink[];
};

export type MemberProfile = MemberPublication & {
  verified: boolean;
  membership_id: number;
  display_name: string;
  is_visible: boolean;
  show_attended_events: boolean;
  headline: string;
  institution: string;
  bio: string;
  avatar_url: string | null;
  interests: string[];
  languages: string[];
  education: { institution: string; qualification?: string; year?: string }[];
  github_username: string;
  github_contributions: number | null;
  projects: MemberProject[];
  activity: MemberProfileActivity;
};

export type ProjectDraft = {
  id?: number;
  title: string;
  subtitle?: string;
  tags?: string[];
  public_visible?: boolean;
  description: string;
  links: { label: string; url: string }[];
};

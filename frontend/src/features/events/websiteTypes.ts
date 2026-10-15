export type WebsiteSection = {
  kind: "intro" | "logo" | "speaker" | "track" | "room" | "sponsor" | "faq" | "resource" | "highlight";
  slug: string; title: string; body: string; url: string;
  asset_id: number | null; image_url?: string | null; image_alt_text?: string;
  visibility: "draft" | "published"; position: number;
  headline?: string; organization?: string; website_url?: string; linkedin_url?: string; x_url?: string;
  sponsor_tier?: SponsorTier; icon?: string;
};

export const sponsorTiers = ["platinum", "gold", "silver", "partner", "community_partner"] as const;
export type SponsorTier = typeof sponsorTiers[number];
export const websiteGroups = ["HERO", "ABOUT", "HIGHLIGHTS", "SCHEDULE", "SPEAKERS", "SPONSORS", "VENUE", "FAQ", "RESOURCES"] as const;
export type WebsiteGroup = typeof websiteGroups[number];
export type WebsiteVenue = {
  name: string; address: string; city: string; country: string;
  latitude: number | null; longitude: number | null; map_url: string;
  directions: string; parking: string; public_transport: string; accessibility_notes: string;
};
export const emptyVenue = (): WebsiteVenue => ({ name: "", address: "", city: "", country: "", latitude: null, longitude: null,
  map_url: "", directions: "", parking: "", public_transport: "", accessibility_notes: "" });
export const sectionGroup = (kind: WebsiteSection["kind"]): WebsiteGroup => ({
  intro: "ABOUT", logo: "HERO", highlight: "HIGHLIGHTS", speaker: "SPEAKERS", sponsor: "SPONSORS",
  track: "SCHEDULE", room: "VENUE", faq: "FAQ", resource: "RESOURCES",
})[kind] as WebsiteGroup;
export const orderedGroups = (page: EventWebsite): WebsiteGroup[] => {
  const known = (page.section_order ?? []).filter((key): key is WebsiteGroup => websiteGroups.includes(key as WebsiteGroup));
  return [...new Set([...known, ...websiteGroups])];
};

export type WebsiteSession = {
  slug: string; title: string; body: string; starts_at: string; ends_at: string;
  track: string | null; room: string | null; speakers: string[];
  visibility: "draft" | "published"; delay_minutes?: number;
  effective_starts_at?: string; effective_ends_at?: string;
};

export type EventWebsite = {
  revision: number; released: boolean; inherited: boolean;
  sections: WebsiteSection[]; sessions: WebsiteSession[];
  assets?: { id: number; alt_text: string; size_bytes: number }[];
  tagline?: string; accent_color?: string; section_order?: string[]; section_enabled?: Record<string, boolean>;
  venue?: WebsiteVenue | null;
};

export type WebsiteTarget = { kind: "events" | "event-series"; id: number; makerspaceId: number };

export function contentPayload(page: EventWebsite) {
  return {
    revision: page.revision,
    tagline: page.tagline ?? "", accent_color: page.accent_color ?? "",
    section_order: orderedGroups(page), section_enabled: Object.fromEntries(websiteGroups.map((key) => [key, page.section_enabled?.[key] !== false])),
    venue: page.venue ?? null,
    sections: page.sections.map(({ image_url: _image, image_alt_text: _alt, ...section }) => section),
    sessions: page.sessions.map(({ delay_minutes: _delay, effective_starts_at: _start, effective_ends_at: _end, ...session }) => session),
  };
}

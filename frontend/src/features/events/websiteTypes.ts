import type * as Api from "../../generated/api";

// Input-derived local rows also represent new unsaved sections/sessions without output-only fields.
export type WebsiteSection = Api.WebsiteSectionInput & Partial<Pick<Api.WebsiteSection, "image_url" | "image_alt_text" | "body_rendering">>;
export type WebsiteSession = Api.WebsiteSessionInput & Partial<Pick<Api.WebsiteSession, "delay_minutes" | "effective_starts_at" | "effective_ends_at" | "body_rendering">>;
export type WebsiteDelayTarget = Api.WebsiteDelayTarget;
export type WebsiteVenue = Api.WebsiteVenue;
export const sponsorTiers = ["platinum", "gold", "silver", "partner", "community_partner"] as const;
export type SponsorTier = typeof sponsorTiers[number];
export const websiteGroups = ["HERO", "ABOUT", "HIGHLIGHTS", "SCHEDULE", "SPEAKERS", "SPONSORS", "VENUE", "FAQ", "RESOURCES", "EDITORIAL"] as const;
export type WebsiteGroup = typeof websiteGroups[number];
export const emptyVenue = (): WebsiteVenue => ({ name: "", address: "", city: "", country: "", latitude: null, longitude: null,
  map_url: "", directions: "", parking: "", public_transport: "", accessibility_notes: "" });
export const sectionGroup = (kind: WebsiteSection["kind"]): WebsiteGroup => ({
  intro: "ABOUT", logo: "HERO", highlight: "HIGHLIGHTS", speaker: "SPEAKERS", sponsor: "SPONSORS",
  track: "SCHEDULE", room: "VENUE", faq: "FAQ", resource: "RESOURCES",
  prizes: "SPONSORS", judges: "SPEAKERS", mentors: "SPEAKERS", project_gallery: "HIGHLIGHTS", results: "HIGHLIGHTS",
})[kind] as WebsiteGroup;
export const orderedGroups = (page: { section_order?: string[] }): WebsiteGroup[] => {
  return [...new Set([...(page.section_order ?? []), ...websiteGroups])] as WebsiteGroup[];
};

export type EventWebsite = Omit<Api.Website, "sections" | "sessions" | "editorial_document" | "section_enabled"> & {
  sections: WebsiteSection[]; sessions: WebsiteSession[];
  editorial_document?: import("../publicPages/pageTypes").PageDocument | null;
  section_enabled?: Partial<Api.WebsiteGroupVisibility>;
};
export type WebsiteTarget = { kind: "events" | "event-series"; id: number; makerspaceId: number };
export type PublicEventWebsiteData = Api.PublicWebsite;

export const markdownMode = (policy?: Api.BodyRenderingEnum) => policy === "legacy_literal_v1" ? "legacy_literal" : "restricted";

export function contentPayload(page: EventWebsite) {
  return {
    revision: page.revision,
    tagline: page.tagline ?? "", accent_color: page.accent_color ?? "",
    section_order: orderedGroups(page), section_enabled: Object.fromEntries(websiteGroups.map((key) => [key, page.section_enabled?.[key] !== false])),
    venue: page.venue ?? null,
    ...(page.editorial_document ? { editorial_document: page.editorial_document } : {}),
    sections: page.sections.map(({ image_url: _image, image_alt_text: _alt, body_rendering: _policy, ...section }) => section),
    sessions: page.sessions.map(({ delay_minutes: _delay, effective_starts_at: _start, effective_ends_at: _end, body_rendering: _policy, ...session }) => session),
  };
}

import { t } from "@lingui/core/macro";
import type { PageDocument, PageSection, SectionPayloads, SectionType } from "./pageTypes";

export const sectionLabels: Record<SectionType, string> = {
  about: t`About`, gallery: t`Gallery`, team: t`Team`, upcoming_events: t`Upcoming events`, stats: t`Public stats`,
  testimonials: t`Testimonials`, links: t`Links and socials`, location: t`Location`, linked_makerspaces: t`Linked makerspaces`,
  organization_events: t`Organization events`, functional_content: t`Tools, spaces and activities`,
  membership_plans: t`Membership plans`, sponsors: t`Sponsors`,
  shop: t`Shop`,
  crew: t`Crew`,
};
export const emptyDocument = (): PageDocument => ({ schema_version: 1, cover_mode: "inherit", cover_asset_id: null, accent_choice: "inherit", sections: [] });
export function newSection<K extends SectionType>(type: K): Extract<PageSection, { type: K }> {
  const defaults: SectionPayloads = {
    about: { title: "", markdown: "" }, gallery: { title: "", items: [] }, team: { title: "", entries: [] },
    upcoming_events: { title: "" }, stats: { title: "", show_public_inventory_units: false, show_published_event_count: false, publish_public_member_count: false },
    testimonials: { title: "", entries: [] }, links: { title: "", entries: [] },
    location: { title: "", enabled_publicly: false, source: "entered", address: "", map_url: "", latitude: null, longitude: null, directions: "" },
    linked_makerspaces: { title: "" }, organization_events: { title: "" }, functional_content: {},
    membership_plans: { title: "" }, sponsors: { title: "" },
    shop: { title: "" },
    crew: { title: "" },
  };
  return { id: crypto.randomUUID(), type, enabled: true, payload: defaults[type] } as Extract<PageSection, { type: K }>;
}
export const pageInput = "desk-input min-h-11 w-full min-w-0";
export const pageLabel = "grid min-w-0 gap-1 text-sm font-semibold text-ink";

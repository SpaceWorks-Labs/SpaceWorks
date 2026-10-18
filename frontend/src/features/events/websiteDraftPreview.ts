import type { PublicEventEditorialSection } from "../../generated/api";
import { previewSessions } from "./websiteProgramme";
import { websiteGroups, type EventWebsite, type PublicEventWebsiteData, type WebsiteTarget } from "./websiteTypes";

/** Private local preview only. It never resolves member identities or manufactures public eligibility. */
export function websiteDraftPreview(page: EventWebsite, target: WebsiteTarget): PublicEventWebsiteData {
  const projected = { ...page, sections: page.sections.map(row => ({ ...row, image_url: row.image_url ?? null, image_alt_text: row.image_alt_text ?? "" })),
    section_enabled: page.section_enabled ? Object.fromEntries(websiteGroups.map(group => [group, page.section_enabled?.[group] !== false])) as import("../../generated/api").WebsiteGroupVisibility : undefined };
  const document = page.editorial_document;
  if (!document) return { ...projected, editorial_document: undefined, sessions: previewSessions(page.sessions) };
  const asset = (id: number) => {
    const found = page.assets?.find(row => row.id === id);
    return found ? { url: `/api/v1/admin/${target.kind}/${target.id}/website/assets/${id}`, alt: found.alt_text } : null;
  };
  const sections: PublicEventEditorialSection[] = document.sections.flatMap((section): PublicEventEditorialSection[] => {
    if (!section.enabled) return [];
    switch (section.type) {
      case "about": case "links": case "testimonials": return [section];
      case "gallery": return [{ ...section, payload: { ...section.payload, items: section.payload.items.flatMap(item => {
        const image = asset(item.asset_id); return image ? [{ ...image, caption: item.caption }] : [];
      }) } }];
      case "team": return [{ ...section, payload: { ...section.payload, entries: section.payload.entries.map(entry => entry.kind === "explicit"
        ? { id: entry.id, kind: "explicit" as const, display_name: entry.display_name, role: entry.role, url: entry.url }
        : { id: entry.id, kind: "explicit" as const, display_name: "Linked member · checked on publication", role: entry.role }) } }];
      default: return [];
    }
  });
  const cover = document.cover_mode === "none" ? null : document.cover_mode === "asset" && document.cover_asset_id ? asset(document.cover_asset_id) : page.cover;
  return { ...projected, presentation: undefined, cover, sessions: previewSessions(page.sessions), editorial_document: { ...document, sections } };
}

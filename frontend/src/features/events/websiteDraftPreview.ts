import type { PublicPageSection } from "../publicPages/pageTypes";
import { previewSessions } from "./websiteProgramme";
import type { EventWebsite, WebsiteTarget } from "./websiteTypes";

/** Private local preview only. It never resolves member identities or manufactures public eligibility. */
export function websiteDraftPreview(page: EventWebsite, target: WebsiteTarget): EventWebsite {
  const document = page.editorial_document;
  if (!document) return { ...page, sessions: previewSessions(page.sessions) };
  const asset = (id: number) => {
    const found = page.assets?.find(row => row.id === id);
    return found ? { url: `/api/v1/admin/${target.kind}/${target.id}/website/assets/${id}`, alt: found.alt_text } : null;
  };
  const sections: PublicPageSection[] = document.sections.flatMap((section): PublicPageSection[] => {
    if (!section.enabled) return [];
    switch (section.type) {
      case "about": case "links": case "testimonials": return [section];
      case "gallery": return [{ ...section, payload: { ...section.payload, items: section.payload.items.flatMap(item => {
        const image = asset(item.asset_id); return image ? [{ ...image, caption: item.caption }] : [];
      }) } }];
      case "team": return [{ ...section, payload: { ...section.payload, entries: section.payload.entries.map(entry => entry.kind === "explicit"
        ? { id: entry.id, display_name: entry.display_name, role: entry.role, url: entry.url }
        : { id: entry.id, display_name: "Linked member · checked on publication", role: entry.role }) } }];
      default: return [];
    }
  });
  const cover = document.cover_mode === "none" ? null : document.cover_mode === "asset" && document.cover_asset_id ? asset(document.cover_asset_id) : page.cover;
  return { ...page, presentation: undefined, cover, sessions: previewSessions(page.sessions), editorial_projection: { schema_version: 1, sections } };
}

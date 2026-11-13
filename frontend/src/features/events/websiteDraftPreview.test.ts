import { describe, expect, it } from "vitest";
import { websiteDraftPreview } from "./websiteDraftPreview";
import { websiteGroups, type EventWebsite, type WebsiteTarget } from "./websiteTypes";

const target = { kind: "events", id: 9 } as unknown as WebsiteTarget;
const base = (over: Record<string, unknown> = {}): EventWebsite => ({ sections: [], sessions: [], ...over }) as unknown as EventWebsite;
const doc = (over: Record<string, unknown> = {}) => ({ cover_mode: "inherit", cover_asset_id: null, sections: [], ...over });
const INHERITED = { url: "/img/event.png", alt: "Event" };

describe("websiteDraftPreview without an editorial document", () => {
  it("fills missing section image fields with null and empty alt text", () => {
    const out = websiteDraftPreview(base({ sections: [{ id: 1 }, { id: 2, image_url: "/a.png", image_alt_text: "A" }] }), target);
    expect(out.sections).toEqual([{ id: 1, image_url: null, image_alt_text: "" }, { id: 2, image_url: "/a.png", image_alt_text: "A" }]);
  });
  it("leaves group visibility undefined when the page has none, and defaults each group to shown otherwise", () => {
    expect(websiteDraftPreview(base(), target).section_enabled).toBeUndefined();
    const out = websiteDraftPreview(base({ section_enabled: { FAQ: false, HERO: true } }), target);
    expect(Object.keys(out.section_enabled!)).toEqual([...websiteGroups]);
    expect(out.section_enabled).toMatchObject({ FAQ: false, HERO: true, ABOUT: true, EDITORIAL: true });
  });
  it("uses the page cover, then the inherited artwork, then nothing", () => {
    expect(websiteDraftPreview(base({ cover: { url: "/own.png", alt: "Own" } }), target, INHERITED).cover).toEqual({ url: "/own.png", alt: "Own" });
    expect(websiteDraftPreview(base(), target, INHERITED).cover).toEqual(INHERITED);
    expect(websiteDraftPreview(base(), target).cover).toBeNull();
  });
  it("never carries an editorial document, and previews sessions with their effective times", () => {
    const out = websiteDraftPreview(base({ sessions: [{ slug: "a", title: "A", starts_at: "2026-05-01T10:00:00Z", ends_at: "2026-05-01T11:00:00Z", delay_minutes: 10 }] }), target);
    expect(out.editorial_document).toBeUndefined();
    expect(out.sessions[0].effective_starts_at).toBe("2026-05-01T10:10:00.000Z");
  });
});

describe("websiteDraftPreview with an editorial document", () => {
  const assets = [{ id: 5, alt_text: "Five" }];
  it("drops disabled sections and sections of an unknown type", () => {
    const out = websiteDraftPreview(base({ editorial_document: doc({ sections: [
      { type: "about", enabled: true, payload: { body: "x" } }, { type: "links", enabled: false, payload: {} }, { type: "mystery", enabled: true, payload: {} },
      { type: "testimonials", enabled: true, payload: { items: [] } }] }) }), target);
    expect(out.editorial_document!.sections.map(s => s.type)).toEqual(["about", "testimonials"]);
  });
  it("resolves gallery items to the admin asset URL with captions and drops items whose asset is missing", () => {
    const out = websiteDraftPreview(base({ assets, editorial_document: doc({ sections: [{ type: "gallery", enabled: true,
      payload: { items: [{ asset_id: 5, caption: "Cap" }, { asset_id: 6, caption: "Gone" }] } }] }) }), target);
    expect(out.editorial_document!.sections[0]).toMatchObject({ type: "gallery", payload: { items: [{ url: "/api/v1/admin/events/9/website/assets/5", alt: "Five", caption: "Cap" }] } });
  });
  it("shows a gallery with no assets list as empty", () => {
    const out = websiteDraftPreview(base({ editorial_document: doc({ sections: [{ type: "gallery", enabled: true, payload: { items: [{ asset_id: 5, caption: "c" }] } }] }) }), target);
    expect((out.editorial_document!.sections[0] as { payload: { items: unknown[] } }).payload.items).toEqual([]);
  });
  it("never resolves a linked member: it shows a placeholder name, keeping only the role", () => {
    const out = websiteDraftPreview(base({ editorial_document: doc({ sections: [{ type: "team", enabled: true, payload: { entries: [
      { id: 1, kind: "explicit", display_name: "Ann", role: "Lead", url: "https://x.org", extra: "dropped" },
      { id: 2, kind: "member", role: "Mentor", member_id: 77, display_name: "Secret" }] } }] }) }), target);
    const entries = (out.editorial_document!.sections[0] as { payload: { entries: unknown[] } }).payload.entries;
    expect(entries).toEqual([{ id: 1, kind: "explicit", display_name: "Ann", role: "Lead", url: "https://x.org" },
      { id: 2, kind: "explicit", display_name: "Linked member · checked on publication", role: "Mentor" }]);
  });
  it("resolves the cover from the document: none, a chosen asset, or the inherited fallbacks", () => {
    const cover = (over: Record<string, unknown>, extra: Record<string, unknown> = {}, inherited = INHERITED) =>
      websiteDraftPreview(base({ assets, editorial_document: doc(over), ...extra }), target, inherited).cover;
    expect(cover({ cover_mode: "none" })).toBeNull();
    expect(cover({ cover_mode: "asset", cover_asset_id: 5 })).toEqual({ url: "/api/v1/admin/events/9/website/assets/5", alt: "Five" });
    expect(cover({ cover_mode: "asset", cover_asset_id: 99 })).toBeNull();
    expect(cover({ cover_mode: "asset", cover_asset_id: null })).toEqual(INHERITED);
    expect(cover({ cover_mode: "inherit" })).toEqual(INHERITED);
    expect(cover({ cover_mode: "inherit" }, { cover: { url: "/own.png", alt: "Own" } })).toEqual({ url: "/own.png", alt: "Own" });
  });
  it("clears the presentation so a draft never claims publication", () => expect(websiteDraftPreview(base({ presentation: { theme: "x" }, editorial_document: doc() }), target).presentation).toBeUndefined());
});

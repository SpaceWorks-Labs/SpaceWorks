import { emptyDocument } from "./documentDefaults";
import type { EditorState, PublicPageProjection } from "./pageTypes";

/** Plan §10 examples for L2 tests; the integrator replaces aliases with L1's generated schema. */
export function editorFixture(overrides: Partial<EditorState> = {}): EditorState {
  return { kind: "makerspace", owner_id: 7, version: 2, handle: "forge", draft_revision_id: "10000000-0000-4000-8000-000000000001",
    published_revision_id: "10000000-0000-4000-8000-000000000002", assets: [],
    capabilities: { allowed_section_types: ["about", "gallery", "team", "upcoming_events", "stats", "testimonials", "links", "location", "functional_content"],
      required_groups: ["functional_content"], palette_choices: ["inherit", "maker_teal", "workshop_orange", "citron", "sky_blue", "warm_yellow"],
      can_edit_details: true, can_publish: true, can_upload: true, storage_remaining_bytes: 10_000_000 },
    limits: { max_sections: 20, max_assets: 50, max_upload_bytes: 5_000_000 },
    document: { ...emptyDocument(), sections: [
      { id: "20000000-0000-4000-8000-000000000001", type: "about", enabled: true, payload: { title: "Our story", markdown: "Saved story" } },
      { id: "20000000-0000-4000-8000-000000000002", type: "functional_content", enabled: true, payload: {} },
    ] }, ...overrides };
}
export function projectionFixture(overrides: Partial<PublicPageProjection> = {}): PublicPageProjection {
  return { schema_version: 1, kind: "makerspace", canonical_url: "https://space.example/forge", title: "Forge", description: "Build together.",
    publication_token: "released-2", cover: null, presentation: { accent_choice: "inherit", resolved_theme: { primary_color: "#9375ad" } },
    sections: [{ id: "20000000-0000-4000-8000-000000000001", type: "about", payload: { title: "Our story", markdown: "Published story" } },
      { id: "20000000-0000-4000-8000-000000000002", type: "functional_content", payload: { links: [] } }], ...overrides };
}

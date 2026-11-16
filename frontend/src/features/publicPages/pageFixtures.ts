import { t } from "@lingui/core/macro";
import { emptyDocument } from "./documentDefaults";
import type { EditorState, PublicPageProjection } from "./pageTypes";
import editorContract from "./fixtures/makerspace_editor.json";
import { deriveBrandPalette } from "../../lib/brandColours";

/** Capabilities and limits copied from backend serializer fixtures. */
export function editorFixture(overrides: Partial<EditorState> = {}): EditorState {
  return { kind: "makerspace", owner_id: 7, version: 2, handle: "forge", draft_revision_id: "10000000-0000-4000-8000-000000000001",
    published_revision_id: "10000000-0000-4000-8000-000000000002", assets: [],
    capabilities: editorContract.capabilities as EditorState["capabilities"],
    limits: editorContract.limits,
    document: { ...emptyDocument(), sections: [
      { id: "20000000-0000-4000-8000-000000000001", type: "about", enabled: true, payload: { title: t`Our story`, markdown: "Saved story" } },
      { id: "20000000-0000-4000-8000-000000000002", type: "functional_content", enabled: true, payload: {} },
    ] }, ...overrides };
}
const resolvedPalette = (mode: "light" | "dark") => {
  const { pairs: _pairs, ...palette } = deriveBrandPalette({ primary_color: "#9375ad" }, mode);
  return palette;
};
export function projectionFixture(overrides: Partial<PublicPageProjection> = {}): PublicPageProjection {
  return { schema_version: 1, kind: "makerspace", canonical_url: "https://space.example/forge", title: t`Forge`, description: t`Build together.`,
    publication_token: "10000000-0000-4000-8000-000000000002", cover: null, presentation: { accent_choice: "inherit", resolved_theme: { theme_config: { primary_color: "#9375ad" }, light: resolvedPalette("light"), dark: resolvedPalette("dark") } },
    sections: [{ id: "20000000-0000-4000-8000-000000000001", type: "about", enabled: true, payload: { title: t`Our story`, markdown: "Published story" } },
      { id: "20000000-0000-4000-8000-000000000002", type: "functional_content", enabled: true, payload: { links: [] } }], ...overrides };
}

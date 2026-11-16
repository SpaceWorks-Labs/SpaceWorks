import { describe, expect, it } from "vitest";
import fixture from "../../../../../backend/tests/events/programme/contracts/fixtures/template-seed-v2.json";
import { duplicate, reorder, safeDesignExport, STOCKS, upgradeDocument, type LayerDocument } from "./layout";

describe("E consumes G's ARTWORK contract", () => {
  it("uses exactly the six physical stocks", () => { expect(STOCKS).toEqual(fixture.stocks); });
  it("keeps immutable documents independent from the server query cache", () => {
    const input = fixture.seed.document as LayerDocument;
    const upgraded = upgradeDocument(input);
    upgraded.layers[0].text = "edited";
    expect(input.layers[0].text).toBe("{{name}}");
  });
  it("reorders by stable IDs and contiguous order, without changing bindings", () => {
    const layers = fixture.seed.document.layers as LayerDocument["layers"];
    const result = reorder(layers, 0, 2);
    expect(result[2].id).toBe(layers[0].id);
    expect(result.map((row) => row.order)).toEqual([0, 1, 2, 3]);
    expect(result[2].text).toBe("{{name}}");
  });
  it("duplicates with a new identity and enforces the 20-layer limit", () => {
    const layers = fixture.seed.document.layers as LayerDocument["layers"];
    const added = duplicate(layers, layers[0].id);
    expect(added[4].id).not.toBe(layers[0].id);
    expect(added[4].text).toBe(layers[0].text);
    const twenty = Array.from({ length: 20 }, (_, order) => ({ ...layers[0], id: crypto.randomUUID(), order }));
    expect(duplicate(twenty, twenty[0].id)).toBe(twenty);
  });
  it("exports typed resource slots without a member image or real check-in payload", () => {
    const text = safeDesignExport(fixture.badge_seed.document as LayerDocument);
    expect(text).toContain("event_credential_qr"); expect(text).toContain("selected_member_photo");
    expect(text).not.toContain("SWEC2."); expect(text).not.toContain("https:");
  });
});

import { describe, expect, it } from "vitest";

import { badgeDesignFile, badgeSampleValues, blankBadge, DESIGN_STOCKS, isSeedable, mergeTags, parseBadgeDesignFile,
  stockSize, validCustomSide } from "./badgeStocks";

describe("badge stocks (G13)", () => {
  it("adds A6 landscape and keeps seeds on the six frozen stocks", () => {
    expect(DESIGN_STOCKS["a6-landscape"]).toEqual([148, 105]);
    expect(isSeedable("cr80-landscape")).toBe(true);
    expect(isSeedable("a6-landscape")).toBe(false);
    expect(isSeedable("custom")).toBe(false);
    expect(stockSize("custom", { width: 90, height: 60 })).toEqual([90, 60]);
  });

  it("accepts custom sides of 40-300 mm in 0.1 mm steps", () => {
    expect([40, 120.5, 300].every(validCustomSide)).toBe(true);
    expect([39.9, 300.1, 60.25, Number.NaN].some(validCustomSide)).toBe(false);
  });

  it("starts a blank badge with the check-in QR slot the server requires", () => {
    const document = blankBadge(148, 105);
    expect(document.layers.map((layer) => layer.type)).toEqual(["text", "text", "event_credential_qr"]);
    const qr = document.layers[2];
    expect(qr.width_mm).toBeGreaterThanOrEqual(20);
    expect(qr.x_mm + qr.width_mm).toBeLessThanOrEqual(148);
  });

  it("round-trips the versioned design file and still reads a bare document", () => {
    const document = blankBadge(90, 60);
    const parsed = parseBadgeDesignFile(badgeDesignFile(document, "custom"));
    expect(parsed).toEqual({ document, stock: "custom" });
    expect(parseBadgeDesignFile(JSON.stringify(document))).toEqual({ document, stock: null });
  });

  it("refuses other kinds, newer versions and broken JSON with plain messages", () => {
    expect(() => parseBadgeDesignFile("{")).toThrow("valid JSON");
    expect(() => parseBadgeDesignFile(JSON.stringify({ kind: "other", version: 2 }))).toThrow("not a Space Works badge");
    expect(() => parseBadgeDesignFile(JSON.stringify({ kind: "spaceworks-badge-design", version: 3 }))).toThrow("newer version");
  });

  it("previews short and long names without changing the stored tags", () => {
    expect(mergeTags("{{name}} · {{event}}", badgeSampleValues(false))).toBe("Priya Raman · Spring Build Night");
    expect(mergeTags("{{name}}", badgeSampleValues(true))).toBe("Alexandra Montgomery-Fitzgerald");
    expect(mergeTags("{{unknown}}", badgeSampleValues(false))).toBe("{{unknown}}");
  });
});

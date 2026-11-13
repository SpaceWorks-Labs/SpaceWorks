import { describe, expect, it } from "vitest";
import { FEATURE_DEFINITIONS, isSecurityFeature } from "../../../lib/features";
import { moduleKeys } from "../../../lib/moduleLabels";
import { featureAreas, featuresByArea, moduleDefault } from "./featureAreas";

// The area catalogue predates the module-by-module page; it still decides each module's docs page and default.
describe("featureAreas", () => {
  it("places every module key the frontend knows in exactly one area", () => {
    const placed = featureAreas().flatMap(area => area.modules as string[]);
    expect([...placed].sort()).toEqual([...moduleKeys()].sort());
    expect(new Set(placed).size).toBe(placed.length);
  });

  it("lists every product feature switch once, and keeps security switches out", () => {
    const listed = Object.values(featuresByArea()).flat().map(feature => feature.key);
    const product = FEATURE_DEFINITIONS.filter(feature => !isSecurityFeature(feature.key) && !feature.key.startsWith("machines.cert"));
    expect(listed.filter(key => isSecurityFeature(key))).toEqual([]);
    expect(new Set(listed).size).toBe(listed.length);
    expect(listed.length).toBeGreaterThan(product.length - 5);
  });

  it("states each module's default, and lists ID cards and wallet passes under membership", () => {
    expect(moduleDefault("public_inventory")).toBe("always");
    expect(moduleDefault("events")).toBe("off");
    expect(moduleDefault("machines")).toBe("on");
    const membership = featureAreas().find(area => area.key === "membership")!;
    expect(membership.gets).toContain("Card designer for member cards and staff ID cards, with numbering");
    expect(membership.gets).toContain("Wallet passes and a QR that anyone can check");
  });
});

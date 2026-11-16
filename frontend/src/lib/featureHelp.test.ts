import { expect, it } from "vitest";
import { FEATURE_DEFINITIONS } from "./features";
import { featureHelp } from "./featureHelp";

it("gives every feature switch a short, jargon-free line", () => {
  for (const feature of FEATURE_DEFINITIONS) {
    const help = featureHelp(feature.key);
    expect(help, feature.key).toBeTruthy();
    expect(help!.length, feature.key).toBeLessThanOrEqual(200);
    expect(help, feature.key).not.toMatch(/\b[a-z]+_[a-z_]+\b|tenant|capabilit|\bL\d+\b|#\d+|\]\(/i);
  }
});

import { describe, expect, it } from "vitest";

import { FEATURE_DEFINITIONS, INVENTORY_CHILD_FEATURES, capabilityOn } from "./features";
import { RETIRED_FEATURES } from "./retiredFeatures";

// Mutation-testing pins (decision 457) for the console's effective-switch reader.
const withParent = FEATURE_DEFINITIONS.find(feature => feature.parent_module && !INVENTORY_CHILD_FEATURES.has(feature.key))!;
const parentless = FEATURE_DEFINITIONS.find(feature => !feature.parent_module && !INVENTORY_CHILD_FEATURES.has(feature.key))!;

describe("capabilityOn", () => {
  it("is off without a makerspace, without a stored list, or when the key is not stored", () => {
    expect(capabilityOn(undefined, parentless.key)).toBe(false);
    expect(capabilityOn({}, parentless.key)).toBe(false);
    expect(capabilityOn({ enabled_features: [] }, parentless.key)).toBe(false);
    expect(capabilityOn({ enabled_features: ["other.key"] }, parentless.key)).toBe(false);
  });
  it("is on for a stored parentless key, and for an unknown stored key (no definition, no parent)", () => {
    expect(capabilityOn({ enabled_features: [parentless.key] }, parentless.key)).toBe(true);
    expect(capabilityOn({ enabled_features: ["no.such.key"] }, "no.such.key")).toBe(true);
  });
  it("a retired switch reads off however it is stored", () => {
    for (const key of RETIRED_FEATURES) expect(capabilityOn({ enabled_features: [key, "loans.enabled"], enabled_modules: [] }, key)).toBe(false);
  });
  it("an inventory child needs the Inventory master (loans.enabled) as well", () => {
    const child = [...INVENTORY_CHILD_FEATURES].find(key => !RETIRED_FEATURES.has(key) && !FEATURE_DEFINITIONS.find(f => f.key === key)?.parent_module)
      ?? [...INVENTORY_CHILD_FEATURES].find(key => !RETIRED_FEATURES.has(key))!;
    const parent = FEATURE_DEFINITIONS.find(f => f.key === child)?.parent_module;
    const modules = parent ? [parent] : [];
    expect(capabilityOn({ enabled_features: [child], enabled_modules: modules }, child)).toBe(false);
    expect(capabilityOn({ enabled_features: [child, "loans.enabled"], enabled_modules: modules }, child)).toBe(true);
  });
  it("a feature with a parent module also needs that module installed, and a missing module list means none", () => {
    const parent = withParent.parent_module!;
    const features = [withParent.key, "loans.enabled"];
    expect(capabilityOn({ enabled_features: features, enabled_modules: [parent] }, withParent.key)).toBe(true);
    expect(capabilityOn({ enabled_features: features, enabled_modules: ["some.other.module"] }, withParent.key)).toBe(false);
    expect(capabilityOn({ enabled_features: features, enabled_modules: [] }, withParent.key)).toBe(false);
    expect(capabilityOn({ enabled_features: features }, withParent.key)).toBe(false);
  });
});

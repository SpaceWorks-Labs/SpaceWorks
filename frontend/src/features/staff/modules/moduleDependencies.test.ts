import { describe, expect, it } from "vitest";

import type { ModuleGroup } from "../ModuleSettingsRows";
import { buildAreas, prerequisites, type FeatureRequirements } from "./moduleModel";
import { dependentFeatures, planFeature, planModule } from "./modulePlans";
import { row } from "./test/moduleFixtures";

// Arch review 7: the console plans from the server's canonical `feature_requirements`, not just
// `parent_module`, so it never offers a switch the capability validator then refuses.
const REQUIREMENTS: FeatureRequirements = {
  "machines.integrations": { modules: ["machines"], features: [] },
  "machines.integrations.access": { modules: ["machines", "devices"], features: ["machines.integrations"] },
  "machines.integrations.video": { modules: ["machines"], features: ["machines.integrations"] },
  "bookings.recurring": { modules: ["bookings"], features: [] },
};

const groups = (installed: { machines?: boolean; devices?: boolean; bookings?: boolean } = {}) => [
  { key: "machines", label: "Machines", description: "", always_on: false, installed_count: 0, module_count: 2, modules: [
    row("machines", "Machines", { installed: !!installed.machines, required_by: [] }),
    row("devices", "Devices", { installed: !!installed.devices, required_by: [] })] },
  { key: "bookings", label: "Bookings", description: "", always_on: false, installed_count: 0, module_count: 1,
    modules: [row("bookings", "Bookings", { installed: !!installed.bookings })] },
] as unknown as ModuleGroup[];

const feature = (areas: ReturnType<typeof buildAreas>, key: string) =>
  areas.flatMap(area => area.cards).flatMap(card => card.features).find(item => item.key === key)!;

describe("canonical feature dependencies", () => {
  it("resolves prerequisites transitively from the server's requirements", () => {
    expect(prerequisites("machines.integrations.access", REQUIREMENTS)).toEqual({
      modules: ["machines", "devices"], features: ["machines.integrations"] });
    // An older server without the map: the parent module only, as before.
    expect(prerequisites("bookings.recurring", {})).toEqual({ modules: ["bookings"], features: [] });
  });

  it("marks a feature as needing a non-parent module the registry requires", () => {
    const areas = buildAreas(groups({ machines: true }), ["machines.integrations"], {}, REQUIREMENTS);
    expect(feature(areas, "machines.integrations.access").needs).toMatchObject({ kind: "module", key: "devices", label: "Devices" });
    expect(feature(areas, "machines.integrations.video").needs).toBeNull();
  });

  it("switches every missing module and feature on before the feature, in one confirmed plan", () => {
    const areas = buildAreas(groups(), [], {}, REQUIREMENTS);
    const plan = planFeature(areas, feature(areas, "machines.integrations.access"), true);
    expect(plan.steps).toEqual([
      { kind: "module", key: "machines", action: "install" },
      { kind: "module", key: "devices", action: "install" },
      { kind: "features", add: ["machines.integrations", "machines.integrations.access"] },
    ]);
    expect(plan.confirm?.lines).toEqual(["Machines", "Devices", "Machine integrations (foundation)"]);
  });

  it("keeps the single-parent confirm and skips the confirm when nothing is missing", () => {
    const off = buildAreas(groups(), [], {}, REQUIREMENTS);
    expect(planFeature(off, feature(off, "bookings.recurring"), true).confirm?.confirmLabel).toBe("Switch on both");
    const ready = buildAreas(groups({ machines: true, devices: true }), ["machines.integrations"], {}, REQUIREMENTS);
    const plan = planFeature(ready, feature(ready, "machines.integrations.access"), true);
    expect(plan.confirm).toBeNull();
    expect(plan.steps).toEqual([{ kind: "features", add: ["machines.integrations.access"] }]);
  });

  it("switches dependents off with a feature they need, and undo can restore them", () => {
    const enabled = ["machines.integrations", "machines.integrations.access", "machines.integrations.video"];
    const areas = buildAreas(groups({ machines: true, devices: true }), enabled, {}, REQUIREMENTS);
    expect(dependentFeatures(areas, "machines.integrations").map(item => item.key).sort())
      .toEqual(["machines.integrations.access", "machines.integrations.video"]);
    const plan = planFeature(areas, feature(areas, "machines.integrations"), false);
    expect(plan.steps).toEqual([{ kind: "features",
      remove: ["machines.integrations.access", "machines.integrations.video", "machines.integrations"] }]);
    expect(plan.confirm?.lines).toEqual(["Adapter access control", "Adapter camera watch"]);
  });

  it("never offers a removal the validator would refuse: a lone feature switches off without a confirm", () => {
    const areas = buildAreas(groups({ machines: true }), ["machines.integrations"], {}, REQUIREMENTS);
    const plan = planFeature(areas, feature(areas, "machines.integrations"), false);
    expect(plan.confirm).toBeNull();
    expect(plan.steps).toEqual([{ kind: "features", remove: ["machines.integrations"] }]);
  });

  it("does not strip Inventory children when the Inventory master switches off (decision 254)", () => {
    const areas = buildAreas(groups(), ["loans.enabled", "inventory.notify_when_back"], {}, REQUIREMENTS);
    expect(dependentFeatures(areas, "loans.enabled")).toEqual([]);
  });

  it("lists and restores features in other areas that need a module being switched off", () => {
    const areas = buildAreas(groups({ machines: true, devices: true }), ["machines.integrations", "machines.integrations.access"], {}, REQUIREMENTS);
    const devices = areas.flatMap(area => area.cards).find(card => card.key === "devices")!;
    const plan = planModule(areas, devices, false);
    expect(plan.confirm?.lines).toContain("Adapter access control");
    expect(plan.steps).toEqual([{ kind: "module", key: "devices", action: "uninstall", restore: ["machines.integrations.access"] }]);
  });
});

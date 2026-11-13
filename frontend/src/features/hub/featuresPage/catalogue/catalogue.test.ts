import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { moduleKeys } from "../../../../lib/moduleLabels";
import { MODULE_GROUP, GROUP_ORDER, moduleFromSlug, moduleSlug, retiredModuleRedirect } from "../moduleGroups";
import { featureAreas } from "../featureAreas";
import { MODULE_LIMIT_KEYS } from "./limitData";
import { REGISTRY } from "./registryData";
import { featureCatalogue, newInRelease } from "./index";

const registry = resolve(__dirname, "../../../../../../backend/apps/makerspaces");

describe("feature catalogue completeness", () => {
  it("has an entry for every module key, with a value, a description and who uses it", () => {
    const catalogue = featureCatalogue();
    expect(Object.keys(catalogue).sort()).toEqual([...moduleKeys()].sort());
    for (const [key, entry] of Object.entries(catalogue)) {
      expect([key, entry.value.length > 0, entry.what.length > 0, entry.roles.length > 0]).toEqual([key, true, true, true]);
      if (!entry.limits.length) expect([key, Boolean(entry.noLimits)]).toEqual([key, true]);
    }
  });

  it("points every New in 0.12.0 card at a real module", () => {
    for (const item of newInRelease()) expect(moduleKeys()).toContain(item.module);
  });

  it("round-trips module slugs and rejects unknown ones", () => {
    for (const key of moduleKeys()) expect(moduleFromSlug(moduleSlug(key))).toBe(key);
    for (const bad of ["", "nope", "constructor", "__proto__", "Machines"]) expect(moduleFromSlug(bad)).toBeNull();
  });
});

describe.skipIf(!existsSync(registry))("module groups mirror the backend registry", () => {
  const source = (file: string) => readFileSync(resolve(registry, file), "utf8");
  const files = () => readdirSync(registry).filter(name => /^module_registry.*\.py$/.test(name));

  it("keeps the group order of module_registry_definitions.GROUPS", () => {
    const text = source("module_registry_definitions.py");
    const constants = Object.fromEntries([...text.matchAll(/^(GROUP_\w+) = "(\w+)"$/gm)].map(match => [match[1], match[2]]));
    const block = text.slice(text.indexOf("GROUPS = ("), text.indexOf("GROUPS_BY_KEY"));
    const order = [...block.matchAll(/GroupDefinition\(\s*(GROUP_\w+)/g)].map(match => constants[match[1]]);
    expect([...GROUP_ORDER]).toEqual(order);
  });

  it("puts every module in the group its ModuleDefinition names", () => {
    const text = source("module_registry_definitions.py");
    const constants = Object.fromEntries([...text.matchAll(/^(GROUP_\w+) = "(\w+)"$/gm)].map(match => [match[1], match[2]]));
    const found: Record<string, string> = {};
    for (const file of files()) {
      for (const chunk of source(file).split("ModuleDefinition(").slice(1)) {
        const key = /^\s*"(\w+)"/.exec(chunk)?.[1];
        const group = /group=(GROUP_\w+)/.exec(chunk)?.[1];
        if (key && group) found[key] = constants[group];
      }
    }
    expect(MODULE_GROUP).toEqual(found);
  });
});

describe("the retired printing module key (decision 340b)", () => {
  it("is never offered: no catalogue entry, group, label key, area or slug of its own", () => {
    expect(Object.keys(featureCatalogue())).not.toContain("printing");
    expect(Object.keys(MODULE_GROUP)).not.toContain("printing");
    expect(moduleKeys()).not.toContain("printing");
    expect(featureAreas().flatMap(area => area.modules as string[])).not.toContain("printing");
    expect(moduleFromSlug("printing")).toBeNull();
  });

  it("moves its limit and report under Machine service and redirects its page there", () => {
    expect(MODULE_LIMIT_KEYS.machine_service).toContain("print");
    expect(MODULE_LIMIT_KEYS.printing).toBeUndefined();
    expect(REGISTRY.machine_service.reports).toContain("printer-service");
    expect(REGISTRY.printing).toBeUndefined();
    expect(retiredModuleRedirect("printing")).toBe("/features/machine-service");
    expect(retiredModuleRedirect("machine-service")).toBeNull();
    expect(retiredModuleRedirect("nope")).toBeNull();
  });
});

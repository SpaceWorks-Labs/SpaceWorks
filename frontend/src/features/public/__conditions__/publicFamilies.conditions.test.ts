import { describe, expect, it } from "vitest";

import type { TenantBootstrap } from "../../../lib/api";
import { preferredPublicFamily, publicFamilies, publicHome, type PublicFamily } from "../../../lib/publicHome";

// Decision 246: which public pages a visitor is offered per module/capability and site switch.
const ALL_MODULES = ["public_inventory", "events", "bookings", "machines", "membership"];
function boot(modules: string[], features: string[] = ["loans.enabled"], makerspace: Record<string, unknown> = {}) {
  return { makerspace: { public_site_enabled: true, public_inventory_enabled: true, ...makerspace }, modules, features } as unknown as TenantBootstrap;
}

describe("public pages offered to a visitor", () => {
  it("lists every family, in display order, with everything on", () => {
    expect(publicFamilies(boot(ALL_MODULES))).toEqual(["inventory", "events", "bookings", "machines", "membership"]);
  });

  it.each<[PublicFamily, string[], string[], Record<string, unknown>]>([
    ["inventory", ["public_inventory"], [], {}],
    ["inventory", [], ["loans.enabled"], {}],
    ["inventory", [], [], { public_inventory_enabled: false }],
    ["events", ["events"], [], {}],
    ["bookings", ["bookings"], [], {}],
    ["machines", ["machines"], [], {}],
    ["membership", ["membership"], [], {}],
  ])("%s disappears when %j / %j are off or the space unpublishes it", (family, offModules, offFeatures, makerspace) => {
    const modules = ALL_MODULES.filter(key => !offModules.includes(key));
    const features = ["loans.enabled"].filter(key => !offFeatures.includes(key));
    expect(publicFamilies(boot(ALL_MODULES))).toContain(family);
    expect(publicFamilies(boot(modules, features, makerspace))).not.toContain(family);
  });

  it("offers nothing, and no overview, when the public site is switched off", () => {
    expect(publicFamilies(boot(ALL_MODULES, ["loans.enabled"], { public_site_enabled: false }))).toEqual([]);
    expect(publicHome(boot(ALL_MODULES, ["loans.enabled"], { public_site_enabled: false }))).toBe("none");
    expect(publicHome(boot([]))).toBe("makerspace");
  });

  it.each([["events", "events"], ["bookings", "bookings"], ["auto", undefined], ["", undefined]])(
    "saved landing choice %j becomes the primary shortcut only while available", (choice, expected) => {
      expect(preferredPublicFamily(boot(ALL_MODULES, ["loans.enabled"], { public_landing_page: choice }))).toBe(expected);
    });

  it("drops a saved landing choice whose module is off", () => {
    expect(preferredPublicFamily(boot(["bookings"], [], { public_landing_page: "events" }))).toBeUndefined();
  });
});

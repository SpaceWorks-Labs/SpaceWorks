import { describe, expect, it } from "vitest";

import type { FeatureDefinition } from "./features";
import { INVENTORY_CHILD_FEATURES, featureEnabled, featureGroup, isSecurityFeature } from "./featureGates";

// Mutation-testing pins (decision 457) for the pure switch helpers.
const def = (key: string, parent_module?: string) => ({ key, parent_module }) as unknown as FeatureDefinition;

describe("featureEnabled", () => {
  it("is exact membership in the list the server sent", () => {
    expect(featureEnabled(["a.b", "c.d"], "c.d")).toBe(true);
    expect(featureEnabled(["a.b"], "c.d")).toBe(false);
    expect(featureEnabled(new Set(["x"]), "x")).toBe(true);
    expect(featureEnabled([], "x")).toBe(false);
  });
});

describe("isSecurityFeature", () => {
  it("is true only for keys that START with security.", () => {
    expect(isSecurityFeature("security.mfa")).toBe(true);
    expect(isSecurityFeature("security.")).toBe(true);
    expect(isSecurityFeature("inventory.security.")).toBe(false);
    expect(isSecurityFeature("xsecurity.mfa")).toBe(false);
    expect(isSecurityFeature("billing.mfa")).toBe(false);
    expect(isSecurityFeature("")).toBe(false);
  });
});

describe("featureGroup", () => {
  it("lists a feature under its parent module when it has one, before any prefix rule", () => {
    expect(featureGroup(def("inventory.kiosk", "machines"))).toBe("machines");
    expect(featureGroup(def("loans.renewals", "events"))).toBe("events");
    expect(featureGroup(def("misc.thing", "bookings"))).toBe("bookings");
  });
  it("puts parentless inventory. and loans. keys under inventory, and everything else under general", () => {
    expect(featureGroup(def("inventory.kiosk"))).toBe("inventory");
    expect(featureGroup(def("loans.enabled"))).toBe("inventory");
    expect(featureGroup(def("security.mfa"))).toBe("general");
    expect(featureGroup(def("reports.inventory.x"))).toBe("general");
    expect(featureGroup(def("x.loans.y"))).toBe("general");
    expect(featureGroup(def("inventory"))).toBe("general");
    expect(featureGroup(def("loans"))).toBe("general");
    expect(featureGroup(def("general.x", ""))).toBe("general");
  });
});

describe("INVENTORY_CHILD_FEATURES", () => {
  it("is exactly the children of the Inventory switch", () => {
    expect([...INVENTORY_CHILD_FEATURES].sort()).toEqual([
      "inventory.contact_self_checkout", "inventory.expected_back", "inventory.issue_reporting", "inventory.kiosk",
      "inventory.maintenance", "inventory.maintenance_reminders", "inventory.notify_when_back", "inventory.repairs",
      "inventory.self_checkout", "inventory.tobuy", "inventory.warranty", "loans.kit_checklist", "loans.limits",
      "loans.pickup_windows", "loans.renewals", "loans.reservations", "loans.waitlist", "loans.withdrawals",
    ]);
  });
});

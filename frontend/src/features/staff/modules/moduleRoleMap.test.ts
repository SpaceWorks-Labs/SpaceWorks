import { describe, expect, it } from "vitest";
import { MODULE_ACTIONS, MEMBER_MODULES, roleUsesModule, runsWholeSpace } from "./moduleRoleMap";
import { moduleKeys } from "../../../lib/moduleLabels";

const role = (slug: string, granted_actions: string[]) => ({ slug, name: slug, granted_actions });

describe("module to role mapping", () => {
  it("maps every registered module key", () => {
    const keys = moduleKeys();
    expect(keys.length).toBeGreaterThan(30);
    expect(Object.keys(MODULE_ACTIONS).sort()).toEqual([...keys].sort());
    for (const key of keys) expect(MODULE_ACTIONS).toHaveProperty(key);
  });
  it("lets the Space Manager use everything", () => {
    const manager = role("space_manager", ["manage_makerspace"]);
    expect(runsWholeSpace(manager)).toBe(true);
    for (const key of Object.keys(MODULE_ACTIONS)) expect(roleUsesModule(manager, key)).toBe(true);
  });
  it("derives an Inventory Manager's modules from the actions they hold", () => {
    const manager = role("inventory_manager", ["view_inventory", "edit_inventory", "manage_qr", "accept_request"]);
    expect(roleUsesModule(manager, "qr_management")).toBe(true);
    expect(roleUsesModule(manager, "stocktake")).toBe(true);
    expect(roleUsesModule(manager, "events")).toBe(false);
    expect(roleUsesModule(manager, "shop")).toBe(false);
  });
  it("follows implied actions: a Machine Manager reaches printing and service handover", () => {
    const manager = role("machine_manager", ["manage_machines"]);
    expect(roleUsesModule(manager, "machines")).toBe(true);
    // The 3D print queue is part of Machine service (340b): a print-desk role reaches it through manage_printing.
    expect(roleUsesModule(role("print-desk", ["manage_printing"]), "machine_service")).toBe(true);
    expect(roleUsesModule(manager, "machine_service")).toBe(true);
    expect(roleUsesModule(manager, "bookings")).toBe(false);
  });
  it("shows a custom role only what its granted actions reach", () => {
    const frontDesk = role("front-desk", ["issue_direct_loan", "upload_evidence"]);
    expect(roleUsesModule(frontDesk, "guest_handover")).toBe(true);
    expect(roleUsesModule(frontDesk, "evidence_uploads")).toBe(true);
    expect(roleUsesModule(frontDesk, "payments")).toBe(false);
  });
  it("gives the Member role the member-facing modules", () => {
    const member = role("member", []);
    for (const key of MEMBER_MODULES) expect(roleUsesModule(member, key)).toBe(true);
    expect(roleUsesModule(member, "machines")).toBe(false);
  });
});

import { describe, expect, it } from "vitest";
import type { ModuleRow } from "../ModuleSettingsRows";
import type { AreaModel, CardModel, FeatureModel } from "./moduleModel";
import { dependentFeatures, inverse, offOrder, planArea, planFeature, planModule, type Step } from "./modulePlans";

const feat = (key: string, over: Partial<FeatureModel> = {}): FeatureModel => ({ key, label: key.toUpperCase(), on: false, needs: null, requiresModules: [], requiresFeatures: [], ...over });
const card = (key: string, over: Omit<Partial<CardModel>, "row"> & { row?: Partial<ModuleRow> | null } = {}): CardModel => {
  const { row, ...rest } = over;
  return { key, label: key[0].toUpperCase() + key.slice(1), description: "", areaKey: "a", features: [], on: false, lock: null,
    row: row === null ? null : { key, label: key, description: "", installed: !!rest.on, core: false, available: true, requires: [], pulls_in: [], required_by: [], workflows: [], ...row } as never, ...rest };
};
const area = (cards: CardModel[], over: Partial<AreaModel> = {}): AreaModel => ({ key: "a", label: "Area", description: "", alwaysOn: false, cards, ...over });

describe("offOrder", () => {
  it("puts dependents before the module they need, once each, following required_by transitively", () => {
    const areas = [area([card("a", { row: { required_by: ["b", "c"] } }), card("b", { row: { required_by: ["c"] } }), card("c")])];
    expect(offOrder(areas, ["a"])).toEqual(["c", "b", "a"]);
  });
  it("includes a key that has no card as itself", () => expect(offOrder([area([])], ["ghost"])).toEqual(["ghost"]));
  it("does not loop on a cycle", () => {
    const areas = [area([card("a", { row: { required_by: ["b"] } }), card("b", { row: { required_by: ["a"] } })])];
    expect(offOrder(areas, ["a"])).toEqual(["b", "a"]);
  });
});

describe("dependentFeatures", () => {
  const areas = [area([card("m", { features: [feat("x", { on: true }), feat("y", { on: true, requiresFeatures: ["x"] }), feat("z", { on: false, requiresFeatures: ["x"] })] })])];
  it("lists switched-on features that need the key", () => expect(dependentFeatures(areas, "x").map(f => f.key)).toEqual(["y"]));
  it("never lists the Inventory master's children (decision 254)", () => {
    const inv = [area([card("m", { features: [feat("loans.enabled", { on: true }), feat("loans.kiosk", { on: true, requiresFeatures: ["loans.enabled"] })] })])];
    expect(dependentFeatures(inv, "loans.enabled")).toEqual([]);
  });
});

describe("planModule", () => {
  it("switching on a module with no extras needs no confirmation", () => {
    const c = card("a");
    expect(planModule([area([c])], c, true)).toEqual({ steps: [{ kind: "module", key: "a", action: "install" }], touched: ["a"], summary: "A switched on.", confirm: null });
  });
  it("switching on lists the other areas it pulls in", () => {
    const c = card("a", { row: { pulls_in: ["b"] } });
    const plan = planModule([area([c, card("b")])], c, true);
    expect(plan.touched).toEqual(["a", "b"]);
    expect(plan.confirm).toEqual({ title: "Switch on A?", message: "A needs other areas, which will be switched on with it.", lines: ["B"], confirmLabel: "Switch on" });
  });
  it("labels a pulled-in module with no card by its key", () => {
    const c = card("a", { row: { pulls_in: ["ghost"] } });
    expect(planModule([area([c])], c, true).confirm?.lines).toEqual(["ghost"]);
  });
  it("switching off a lone module with nothing on needs no confirmation", () => {
    const c = card("a", { on: true });
    const plan = planModule([area([c])], c, false);
    expect(plan.steps).toEqual([{ kind: "module", key: "a", action: "uninstall", restore: [] }]);
    expect(plan).toMatchObject({ touched: ["a"], summary: "A switched off.", confirm: null });
  });
  it("switching off with features on hides them and remembers them for undo, skipping not-shipped ones", () => {
    const c = card("a", { on: true, features: [feat("f1", { on: true }), feat("f2", { on: true, lock: "not_shipped" }), feat("f3", { on: false })] });
    const plan = planModule([area([c])], c, false);
    expect(plan.steps).toEqual([{ kind: "module", key: "a", action: "uninstall", restore: ["f1"] }]);
    expect(plan.confirm).toEqual({ title: "Switch off A?", confirmLabel: "Switch off", message: "These features are hidden while A is off. Nothing is deleted.", lines: ["F1", "F2"] });
  });
  it("switching off a needed module switches its dependents off first and says so", () => {
    const a = card("a", { on: true, row: { required_by: ["b"] } }), b = card("b", { on: true });
    const plan = planModule([area([a, b])], a, false);
    expect(plan.steps.map(s => (s as { key: string }).key)).toEqual(["b", "a"]);
    expect(plan.confirm).toMatchObject({ message: "A is needed by other areas, which switch off with it. Their features are hidden too. Nothing is deleted.", lines: ["B (needs A)"] });
  });
  it("names features elsewhere that need the module and restores them on undo", () => {
    const a = card("a", { on: true });
    const other = card("o", { on: true, features: [feat("ext", { on: true, requiresModules: ["a"] })] });
    const plan = planModule([area([a, other])], a, false);
    expect(plan.steps).toEqual([{ kind: "module", key: "a", action: "uninstall", restore: ["ext"] }]);
    expect(plan.confirm?.lines).toEqual(["EXT"]);
  });
});

describe("planFeature (off)", () => {
  const m = card("m", { on: true, features: [feat("x", { on: true }), feat("y", { on: true, requiresFeatures: ["x"] })] });
  it("switches dependents off first in the same save, with a confirmation listing them", () => {
    const plan = planFeature([area([m])], m.features[0], false);
    expect(plan.steps).toEqual([{ kind: "features", remove: ["y", "x"] }]);
    expect(plan).toMatchObject({ touched: ["y", "x"], summary: "X switched off.",
      confirm: { title: "Switch off X?", confirmLabel: "Switch off", lines: ["Y"], message: "These features need X, so they switch off with it. Nothing is deleted." } });
  });
  it("needs no confirmation when nothing depends on it", () => expect(planFeature([area([m])], m.features[1], false).confirm).toBeNull());
  it("always confirms switching off the Inventory master and hides its children without deleting", () => {
    const inv = card("inv", { on: true, features: [feat("loans.enabled", { on: true }), feat("loans.kiosk", { on: true, requiresFeatures: ["loans.enabled"] })] });
    const plan = planFeature([area([inv])], inv.features[0], false);
    expect(plan.steps).toEqual([{ kind: "features", remove: ["loans.enabled"] }]);
    expect(plan.confirm).toEqual({ title: "Switch off Inventory?", confirmLabel: "Switch off", lines: [],
      message: "Borrowing, self-checkout, the kiosk and the other Inventory features are hidden. Nothing is deleted." });
  });
});

describe("planFeature (on)", () => {
  it("is silent when every prerequisite is already on", () => {
    const m = card("m", { on: true, features: [feat("x")] });
    expect(planFeature([area([m])], m.features[0], true)).toEqual({ steps: [{ kind: "features", add: ["x"] }], touched: ["x"], summary: "X switched on.", confirm: null });
  });
  it("offers to switch on the single missing module too, listing what it pulls in", () => {
    const need = card("need", { row: { pulls_in: ["extra"] } }), extra = card("extra");
    const m = card("m", { on: true, features: [feat("x", { requiresModules: ["need"] })] });
    const plan = planFeature([area([m, need, extra])], m.features[0], true);
    expect(plan.steps).toEqual([{ kind: "module", key: "need", action: "install" }, { kind: "features", add: ["x"] }]);
    expect(plan.confirm).toEqual({ title: "Switch on Need too?", confirmLabel: "Switch on both", message: "X only works while Need is on. Switch both on?", lines: ["Extra"] });
  });
  it("switches the Inventory master on silently when it is the only thing missing", () => {
    const m = card("m", { on: true, features: [feat("x", { requiresFeatures: ["loans.enabled"] })] });
    const plan = planFeature([area([m])], m.features[0], true);
    expect(plan.steps).toEqual([{ kind: "features", add: ["loans.enabled", "x"] }]);
    expect(plan.confirm).toBeNull();
  });
  it("confirms and lists every missing module, feature and pulled-in module otherwise", () => {
    const a = card("a", { row: { pulls_in: ["c"] } }), b = card("b"), c = card("c");
    const m = card("m", { on: true, features: [feat("x", { requiresModules: ["a", "b"], requiresFeatures: ["p"] }), feat("p")] });
    const plan = planFeature([area([m, a, b, c])], m.features[0], true);
    expect(plan.steps).toEqual([{ kind: "module", key: "a", action: "install" }, { kind: "module", key: "b", action: "install" }, { kind: "features", add: ["p", "x"] }]);
    expect(plan.touched).toEqual(["a", "b", "p", "x"]);
    expect(plan.confirm).toEqual({ title: "Switch on X?", confirmLabel: "Switch all on", message: "X needs these too. They switch on with it.", lines: ["A", "B", "P", "C"] });
  });
  it("skips prerequisite modules that are already installed or unknown", () => {
    const on = card("on", { on: true });
    const m = card("m", { on: true, features: [feat("x", { requiresModules: ["on", "ghost"] })] });
    expect(planFeature([area([m, on])], m.features[0], true).steps).toEqual([{ kind: "features", add: ["x"] }]);
  });
  it("does not re-add a prerequisite feature that is already on", () => {
    const m = card("m", { on: true, features: [feat("x", { requiresFeatures: ["p"] }), feat("p", { on: true })] });
    expect(planFeature([area([m])], m.features[0], true).steps).toEqual([{ kind: "features", add: ["x"] }]);
  });
});

describe("planArea", () => {
  const a = card("a", { on: true }), b = card("b", { on: false }), locked = card("l", { on: false, lock: "core" }), noRow = card("n", { row: null });
  it("switches on only the open, currently-off modules and confirms", () => {
    const plan = planArea([area([a, b, locked, noRow])], area([a, b, locked, noRow], { label: "Space" }), true);
    expect(plan.steps).toEqual([{ kind: "module", key: "b", action: "install" }]);
    expect(plan.summary).toBe("Space: 1 switched on.");
    expect(plan.confirm).toEqual({ title: "Switch on everything in Space?", confirmLabel: "Switch all on", lines: ["B"],
      message: "These switch on. 1 locked switches stay as they are." });
  });
  it("switches off currently-on modules, dependents first, and says nothing is deleted", () => {
    const x = card("x", { on: true, row: { required_by: ["y"] } }), y = card("y", { on: true });
    const ar = area([x, y], { label: "Space" });
    const plan = planArea([ar], ar, false);
    expect(plan.steps.map(s => (s as { key: string }).key)).toEqual(["y", "x"]);
    expect(plan.summary).toBe("Space: 2 switched off.");
    expect(plan.confirm).toMatchObject({ title: "Switch off everything in Space?", confirmLabel: "Switch all off",
      message: "These switch off and their features are hidden. Nothing is deleted.", lines: ["Y", "X"] });
  });
  it("leaves out dependents that are already off when switching off", () => {
    const x = card("x", { on: true, row: { required_by: ["y"] } }), y = card("y", { on: false });
    const ar = area([x, y]);
    expect(planArea([ar], ar, false).steps.map(s => (s as { key: string }).key)).toEqual(["x"]);
  });
});

describe("inverse", () => {
  it("reverses the order and swaps features add/remove", () => expect(inverse([{ kind: "features", add: ["a"], remove: ["b"] }, { kind: "features", add: ["c"] }])).toEqual([
    { kind: "features", add: undefined, remove: ["c"] }, { kind: "features", add: ["b"], remove: ["a"] }]));
  it("undoes an install with an uninstall", () => expect(inverse([{ kind: "module", key: "m", action: "install" }])).toEqual([{ kind: "module", key: "m", action: "uninstall" }]));
  it("undoes an uninstall with an install and restores the remembered features", () => {
    const steps: Step[] = [{ kind: "module", key: "m", action: "uninstall", restore: ["f"] }];
    expect(inverse(steps)).toEqual([{ kind: "module", key: "m", action: "install" }, { kind: "features", add: ["f"] }]);
  });
  it("adds no feature step when there was nothing to restore", () => expect(inverse([{ kind: "module", key: "m", action: "uninstall", restore: [] }, { kind: "module", key: "n", action: "uninstall" }]))
    .toEqual([{ kind: "module", key: "n", action: "install" }, { kind: "module", key: "m", action: "install" }]));
});

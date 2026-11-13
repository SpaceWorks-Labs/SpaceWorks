import { describe, expect, it } from "vitest";

import { canMoveUnder, orderedUnits, subtreeIds, usableLevels } from "./unitHierarchy";
import type { MemberUnit } from "./unitsApi";

const unit = (id: number, parent: number | null, path: string, level: number, extra: Partial<MemberUnit> = {}): MemberUnit => ({
  id, parent_id: parent, name: `U${id}`, slug: `u${id}`, code: `U${id}`, level, level_name: "", path, sort_order: 0,
  archived: false, has_payment_instructions: false, ...extra,
});
// NORTH(1) > KOCHI(2) > FORT(3); SOUTH(4)
const tree = [unit(3, 2, "/N/K/F/", 2), unit(4, null, "/S/", 0, { name: "A south" }), unit(2, 1, "/N/K/", 1), unit(1, null, "/N/", 0, { name: "B north" })];

describe("unit hierarchy helpers", () => {
  it("orders parents before children, siblings by order then name", () => {
    expect(orderedUnits(tree).map(row => [row.id, row.depth])).toEqual([[4, 0], [1, 0], [2, 1], [3, 2]]);
  });

  it("treats a unit whose parent is out of view (a scoped list) as a root", () => {
    expect(orderedUnits([tree[0], tree[2]]).map(row => [row.id, row.depth])).toEqual([[2, 0], [3, 1]]);
  });

  it("finds a subtree by materialised path", () => {
    expect([...subtreeIds(tree, 1)].sort()).toEqual([1, 2, 3]);
  });

  it("refuses a cycle, an archived parent and a move past the named levels", () => {
    const levels = ["State", "District", "Chapter"];
    expect(canMoveUnder(tree, levels, 1, 3)).toBe(false); // under its own grandchild
    expect(canMoveUnder(tree, levels, 2, 4)).toBe(true); // KOCHI (+FORT) under SOUTH: levels 1-2
    expect(canMoveUnder(tree, levels, 1, 4)).toBe(false); // NORTH's three levels under SOUTH would need four
    expect(canMoveUnder([...tree, unit(5, null, "/X/", 0, { archived: true })], levels, 3, 5)).toBe(false);
    expect(canMoveUnder(tree, levels, 2, null)).toBe(true);
  });

  it("allows four levels until the space names any", () => {
    expect(usableLevels([])).toBe(4);
    expect(usableLevels(["Branch"])).toBe(1);
    expect(canMoveUnder(tree, ["Branch"], 4, 1)).toBe(false);
  });
});

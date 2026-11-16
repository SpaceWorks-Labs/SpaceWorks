import type { MemberUnit } from "./unitsApi";

/** The platform ceiling: a space names at most four levels (`member_units.MAX_LEVELS`). */
export const MAX_LEVELS = 4;

export type UnitRow = MemberUnit & { depth: number };

const byOrder = (a: MemberUnit, b: MemberUnit) => a.sort_order - b.sort_order || a.name.localeCompare(b.name);

/**
 * Depth-first order (parents before children, siblings by sort order then name). A unit whose parent
 * is not in the list (a unit-scoped caller sees only their own subtree) becomes a root, so a scoped
 * list still reads as a tree rather than disappearing.
 */
export function orderedUnits(units: readonly MemberUnit[]): UnitRow[] {
  const ids = new Set(units.map(unit => unit.id));
  const children = new Map<number | null, MemberUnit[]>();
  for (const unit of units) {
    const parent = unit.parent_id !== null && ids.has(unit.parent_id) ? unit.parent_id : null;
    children.set(parent, [...(children.get(parent) ?? []), unit]);
  }
  const rows: UnitRow[] = [];
  const walk = (parent: number | null, depth: number) => {
    for (const unit of [...(children.get(parent) ?? [])].sort(byOrder)) {
      rows.push({ ...unit, depth });
      walk(unit.id, depth + 1);
    }
  };
  walk(null, 0);
  return rows;
}

/** The unit and everything beneath it, by materialised path (the server's own subtree rule). */
export function subtreeIds(units: readonly MemberUnit[], unitId: number): Set<number> {
  const root = units.find(unit => unit.id === unitId);
  if (!root) return new Set();
  return new Set(units.filter(unit => unit.path.startsWith(root.path)).map(unit => unit.id));
}

/** How many levels the space may use: its named levels, or the ceiling until it names any. */
export const usableLevels = (levels: readonly string[]) => (levels.length ? levels.length : MAX_LEVELS);

/** The deepest level number inside a unit's subtree, relative to the unit (0 = no sub-units). */
export function subtreeHeight(units: readonly MemberUnit[], unitId: number): number {
  const root = units.find(unit => unit.id === unitId);
  if (!root) return 0;
  return Math.max(0, ...units.filter(unit => unit.path.startsWith(root.path)).map(unit => unit.level - root.level));
}

/**
 * Whether `unitId` may move under `parentId` (null = top level), mirroring the server's checks so the
 * picker and drop targets offer only moves that can succeed. The server still decides.
 */
export function canMoveUnder(units: readonly MemberUnit[], levels: readonly string[], unitId: number, parentId: number | null) {
  if (parentId === null) return subtreeHeight(units, unitId) < usableLevels(levels);
  const parent = units.find(unit => unit.id === parentId);
  if (!parent || parent.archived || subtreeIds(units, unitId).has(parentId)) return false;
  return parent.level + 1 + subtreeHeight(units, unitId) < usableLevels(levels);
}

/** The name staff see for a level: the space's own, else a plain "Level n". */
export const levelLabel = (levels: readonly string[], level: number, fallback: (n: number) => string) =>
  levels[level]?.trim() || fallback(level + 1);

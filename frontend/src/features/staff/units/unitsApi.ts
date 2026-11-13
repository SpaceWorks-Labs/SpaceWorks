import { t } from "@lingui/core/macro";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { StructuredApiError, staffRequest } from "../../../lib/api";

// Hand-written mirrors of the parity O-B1 staff routes (`admin_api/views_member_units.py`,
// `views_member_unit_links.py`). Swap for `src/generated/api.ts` types once the schema snapshot is
// regenerated at staging. Every route answers a typed 404 while `membership.units` is off.

export type MemberUnit = {
  id: number; parent_id: number | null; name: string; slug: string; code: string; level: number; level_name: string;
  path: string; sort_order: number; archived: boolean; has_payment_instructions: boolean;
};
export type MemberUnitDetail = MemberUnit & {
  payment_instructions: string; effective_payment_instructions: string; effective_instructions_unit_id: number | null;
};
export type LevelTemplate = { key: string; label: string; levels: string[] };
export type MemberUnitList = {
  levels: string[]; templates: LevelTemplate[]; units: MemberUnit[]; limit: number | null; used: number; scoped: boolean;
};
export type UnitInput = { name?: string; parent_id?: number | null; code?: string; payment_instructions?: string; sort_order?: number };
export type UnitAssignment = { membership_id: number; unit: MemberUnit | null };
export type ImportReviewRow = {
  id: number; unit_id: number; review_status: string; row_status: string; name: string; email: string; created_at: string;
};

const space = (id: number) => `/admin/makerspaces/${id}`;
const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

/** One prefix per space, so a tree change can refresh every unit view of that space at once. */
export const unitKeys = {
  all: (id: number) => ["member-units", id] as const,
  list: (id: number, archived: boolean) => ["member-units", id, "list", archived] as const,
  detail: (id: number, unitId: number) => ["member-units", id, "detail", unitId] as const,
  planUnits: (id: number, planId: number) => ["member-units", id, "plan", planId] as const,
  staffScope: (id: number, membershipId: number) => ["member-units", id, "staff-scope", membershipId] as const,
  memberUnit: (id: number, membershipId: number) => ["member-units", id, "member", membershipId] as const,
  reviews: (id: number) => ["member-units", id, "import-reviews"] as const,
};

export const unitsApi = {
  list: (id: number, archived = false) =>
    staffRequest<MemberUnitList>(`${space(id)}/member-units${archived ? "?archived=1" : ""}`),
  detail: (id: number, unitId: number) => staffRequest<MemberUnitDetail>(`${space(id)}/member-units/${unitId}`),
  create: (id: number, input: UnitInput) => staffRequest<MemberUnitDetail>(`${space(id)}/member-units`, json("POST", input)),
  update: (id: number, unitId: number, input: UnitInput) =>
    staffRequest<MemberUnitDetail>(`${space(id)}/member-units/${unitId}`, json("PATCH", input)),
  move: (id: number, unitId: number, parentId: number | null) =>
    staffRequest<MemberUnitDetail>(`${space(id)}/member-units/${unitId}/move`, json("POST", { parent_id: parentId })),
  archive: (id: number, unitId: number) =>
    staffRequest<MemberUnitDetail>(`${space(id)}/member-units/${unitId}/archive`, { method: "POST" }),
  restore: (id: number, unitId: number) =>
    staffRequest<MemberUnitDetail>(`${space(id)}/member-units/${unitId}/restore`, { method: "POST" }),
  setLevels: (id: number, levels: string[]) =>
    staffRequest<{ levels: string[] }>(`${space(id)}/member-unit-levels`, json("PUT", { levels })),
  memberUnit: (id: number, membershipId: number) =>
    staffRequest<UnitAssignment>(`${space(id)}/memberships/${membershipId}/unit`),
  setMemberUnit: (id: number, membershipId: number, unitId: number | null) =>
    staffRequest<UnitAssignment>(`${space(id)}/memberships/${membershipId}/unit`, json("PUT", { unit_id: unitId })),
  staffScope: (id: number, membershipId: number) => staffRequest<UnitAssignment>(`${space(id)}/staff/${membershipId}/unit-scope`),
  setStaffScope: (id: number, membershipId: number, unitId: number | null) =>
    staffRequest<UnitAssignment>(`${space(id)}/staff/${membershipId}/unit-scope`, json("PUT", { unit_id: unitId })),
  planUnits: (id: number, planId: number) => staffRequest<{ unit_ids: number[] }>(`${space(id)}/membership-plans/${planId}/units`),
  setPlanUnits: (id: number, planId: number, unitIds: number[]) =>
    staffRequest<{ unit_ids: number[] }>(`${space(id)}/membership-plans/${planId}/units`, json("PUT", { unit_ids: unitIds })),
  reviews: (id: number) => staffRequest<ImportReviewRow[]>(`${space(id)}/member-import-reviews`),
  decideReview: (id: number, importedId: number, decision: "approve" | "reject") =>
    staffRequest<{ id: number; review_status: string }>(`${space(id)}/member-import-reviews/${importedId}/${decision}`, { method: "POST" }),
};

/** The unit tree of a space. `enabled` false (switch off, no access) never asks. */
export function useMemberUnits(makerspaceId: number, { archived = false, enabled = true } = {}) {
  return useQuery({ queryKey: unitKeys.list(makerspaceId, archived), queryFn: () => unitsApi.list(makerspaceId, archived),
    enabled: enabled && makerspaceId > 0, retry: false, placeholderData: keepPreviousData });
}

/** Friendly copy for the typed refusals; the server's own (translated) message otherwise. */
export function unitErrorText(error: unknown): string {
  const copy: Record<string, string> = {
    member_unit_cycle: t`A unit cannot move under itself or one of its own sub-units.`,
    member_unit_depth: t`That would go deeper than the levels this space has named. Name another level first.`,
    member_unit_archived: t`An archived unit cannot take new units or members. Restore it first.`,
    member_unit_has_children: t`Archive the units beneath it first.`,
    member_unit_code_taken: t`Another unit already uses this code.`,
    member_unit_code_invalid: t`Use 1 to 6 capital letters or digits for the code.`,
    member_unit_code_locked: t`This unit's code is in use, so it can no longer change.`,
    member_unit_levels_in_use: t`A unit still sits on a level you are removing.`,
    member_unit_missing: t`Choose an active unit in this space.`,
    member_units_quota_reached: t`This space has reached its allowance of units.`,
    unit_scope_forbids: t`Your role is limited to one unit, so you can't change this.`,
    import_verify_needs_unit: t`Choose the unit that will review the imported rows.`,
  };
  if (error instanceof StructuredApiError && error.code && copy[error.code]) return copy[error.code];
  return error instanceof Error && error.message ? error.message : t`That did not work. Try again.`;
}

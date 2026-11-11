import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { tenantPublicRequest } from "../../lib/api";

// Mirrors `makerspaces/views_member_units_public.PublicMemberUnitsView` (parity O-B1). Only names,
// codes and levels: never members, counts, payment instructions or archived units.
export type PublicUnit = { code: string; name: string; level: number; level_name: string; parent_code: string | null };
export type PublicUnits = { levels: string[]; units: PublicUnit[]; selected: PublicUnit | null; plan_ids: number[] | null };

/**
 * The join page's unit picker. With `code` the server also resolves that unit and the active plans
 * offered in it (`plan_ids`). A 404 means the space does not use units, so this yields null and the
 * join page shows no picker.
 */
export function usePublicUnits(slug: string, code: string) {
  const query = code ? `?${new URLSearchParams({ code })}` : "";
  return useQuery({ queryKey: ["public", slug, "member-units", code], enabled: Boolean(slug), retry: false,
    placeholderData: keepPreviousData,
    queryFn: () => tenantPublicRequest<PublicUnits>(slug, `/public/${slug}/member-units${query}`).catch(() => null) });
}

/** Units in tree order (parents first), with their depth, for an indented picker. */
export function publicUnitRows(units: readonly PublicUnit[]) {
  const codes = new Set(units.map(unit => unit.code));
  const rows: (PublicUnit & { depth: number })[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const unit of units.filter(item => (item.parent_code !== null && codes.has(item.parent_code) ? item.parent_code : null) === parent)) {
      rows.push({ ...unit, depth });
      walk(unit.code, depth + 1);
    }
  };
  walk(null, 0);
  return rows;
}

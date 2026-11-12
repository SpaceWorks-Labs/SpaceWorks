// Shelf pointer for inventory staff (decision 331): the routes of `apps/devices/views_shelf.py`.
// All of them answer 404 while `machines.integrations` is off; none ever returns a pose.
import { staffRequest } from "../../../lib/api";
import { StructuredApiError } from "../../../lib/api/errors";

export type ShelfTargetType = "storage_location" | "item" | "box";
export type ShelfTarget = { target_type: ShelfTargetType; target_id: string };
export type ShelfLocation = { location: string; item_count: number; covered: boolean };
export type ShelfCheckEntry = { location: string; status: "ok" | "attention"; note: string };
export type ShelfCheck = { id: string; scope_label: string; ok_count: number; attention_count: number; checked_by_name: string; created_at: string };
export type ShelfCheckDetail = ShelfCheck & { entries: ShelfCheckEntry[] };
export type ShelfCheckPage = { count: number; next: string | null; previous: string | null; results: ShelfCheck[] };

const space = (id: number) => `/admin/makerspace/${id}`;
const post = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const shelfKeys = {
  root: (makerspace: number) => ["shelf-pointer", makerspace] as const,
  coverage: (makerspace: number, type: ShelfTargetType, id: string) => ["shelf-pointer", makerspace, "coverage", type, id] as const,
  locations: (makerspace: number, prefix: string) => ["shelf-pointer", makerspace, "locations", prefix] as const,
  checks: (makerspace: number) => ["shelf-pointer", makerspace, "checks"] as const,
};

/** The integrations switch is off, or this person may not use the pointer: the feature simply is not there. */
export const isShelfOff = (error: unknown) => error instanceof StructuredApiError && (error.status === 404 || error.status === 403);

export const shelfApi = {
  coverage: (makerspace: number, targets: ShelfTarget[]) =>
    staffRequest<{ results: (ShelfTarget & { covered: boolean })[] }>(`${space(makerspace)}/shelf-pointer/coverage`, post({ targets })),
  show: (makerspace: number, target: ShelfTarget & { duration_seconds?: number }) =>
    staffRequest<{ sent: number }>(`${space(makerspace)}/shelf-pointer/show`, post(target)),
  clear: (makerspace: number, target?: ShelfTarget) =>
    staffRequest<{ sent: number }>(`${space(makerspace)}/shelf-pointer/clear`, post(target ?? {})),
  locations: (makerspace: number, prefix: string) =>
    staffRequest<ShelfLocation[]>(`${space(makerspace)}/shelf-pointer/locations?prefix=${encodeURIComponent(prefix)}`),
  checks: (makerspace: number) => staffRequest<ShelfCheckPage>(`${space(makerspace)}/shelf-checks`),
  saveCheck: (makerspace: number, body: { scope_label: string; entries: ShelfCheckEntry[] }) =>
    staffRequest<ShelfCheckDetail>(`${space(makerspace)}/shelf-checks`, post(body)),
};

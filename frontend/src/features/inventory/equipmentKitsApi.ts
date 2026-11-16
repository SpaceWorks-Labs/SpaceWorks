import { memberRequest, staffRequest } from "../../lib/api";

export type KitLine = { product_id: number; quantity_per_person: number; kind: "returnable" | "consumable" };
export type SafeKit = { id: number; name: string; version: number; lines: (KitLine & { display_name: string })[] };
export type KitSummary = { id: number; name: string; revision: number; current_version: number; published_for_contexts: boolean; archived: boolean };
export type KitDetail = KitSummary & { lines: KitLine[] };
export type KitPage<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const memberKits = (slug: string, page: number) => memberRequest<KitPage<SafeKit>>(`/public/${encodeURIComponent(slug)}/equipment-kits/?page=${page}`);
export const staffContextKits = (tenant: number, domain: "event" | "booking", resource: number, page: number) =>
  staffRequest<KitPage<SafeKit>>(`/admin/makerspace/${tenant}/${domain === "event" ? "events" : "spaces"}/${resource}/equipment-kits?page=${page}`);
export const staffKits = (tenant: number, page: number, includeArchived = false) => staffRequest<KitPage<KitSummary>>(`/admin/makerspace/${tenant}/equipment-kits?page=${page}${includeArchived ? "&include_archived=true" : ""}`);
export const staffKit = (tenant: number, id: number) => staffRequest<KitDetail>(`/admin/makerspace/${tenant}/equipment-kits/${id}`);
const post = <T>(url: string, body: unknown) => staffRequest<T>(url, { method: "POST", body: JSON.stringify(body) });
export const createKit = (tenant: number, name: string, lines: KitLine[]) => post<KitDetail>(`/admin/makerspace/${tenant}/equipment-kits`, { name, lines });
export const createKitVersion = (tenant: number, id: number, expected_revision: number, name: string, lines: KitLine[]) => post<KitDetail>(`/admin/makerspace/${tenant}/equipment-kits/${id}/versions`, { expected_revision, name, lines });
export const publishKit = (tenant: number, id: number, expected_revision: number, published_for_contexts: boolean) => post<KitSummary>(`/admin/makerspace/${tenant}/equipment-kits/${id}/publication`, { expected_revision, published_for_contexts });
export const archiveKit = (tenant: number, id: number, expected_revision: number, archived: boolean) => post<KitSummary>(`/admin/makerspace/${tenant}/equipment-kits/${id}/archive`, { expected_revision, archived });

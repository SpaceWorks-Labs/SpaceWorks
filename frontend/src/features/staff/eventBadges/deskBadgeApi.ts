// Desk printing data (lane E-B2 routes): one call returns the published designs, the role-to-design map, the
// logos as data URLs and the badge row(s) to print. The same shape is carried inside the offline roster, so a
// desk with no network prints from the encrypted copy. Receipts are idempotent by operation_id.
import { staffRequest } from "../../../lib/api";
import type { BadgeSettings } from "./badgeNormalize";

export type DeskLayer = { id: string; kind: string; x_mm: number; y_mm: number; w_mm: number; h_mm: number } & Record<string, unknown>;
export type DeskDesign = {
  design_id: number; revision: number; stock: string;
  document: { page_width_mm?: number; page_height_mm?: number; mono?: boolean; front: { page_width_mm: number; page_height_mm: number;
    background?: { kind: string; colour?: string }; layers: DeskLayer[] } };
  /** Present for structured badge designs; null for free-canvas ones (drawn from `document`). */
  settings: BadgeSettings | null;
  /** Design image assets (free canvas) as data URLs, so the design prints with no network. */
  assets?: Record<string, string>;
};
export type DeskBadge = {
  registration_id: number; card_id: number | null; name: string; role: string; role_label: string; team: string; crew_kind: string;
  email?: string; answers: Record<string, string>; photo_card_id: number | null; provisional: boolean; status: string;
  checkin_payload: string | null;
  /** The consented photo as a data URL; only on desk reads and only when the design shows a photo. */
  photo?: string | null;
};
export type DeskBundle = { designs: Record<string, DeskDesign>; roles: Record<string, string>; logos: Record<string, string | null> };
export type DeskResponse = DeskBundle & { event: { id: number; title: string }; server_time: string; badge?: DeskBadge; badges?: DeskBadge[] };

export type BadgeReceipt = { operation_id: string; registration_id: number; method: "desk" | "offline" | "bulk"; stock?: string; role?: string; printed_at: string };
export type ReceiptResult = { recorded: number; duplicates: number };

export const STATUS_SETS = ["confirmed", "attendees_without_crew", "crew", "checked_in", "not_checked_in", "all"] as const;
export type StatusSet = typeof STATUS_SETS[number];

export const deskKey = (eventId: number, registrationId?: number) => ["event-badge-desk", eventId, registrationId ?? null] as const;

export function fetchDesk(eventId: number, registrationId?: number, statusSet?: StatusSet): Promise<DeskResponse> {
  const query = registrationId ? `?registration_id=${registrationId}` : statusSet ? `?status_set=${statusSet}` : "";
  return staffRequest<DeskResponse>(`/admin/events/${eventId}/badges/desk${query}`);
}

export function sendDeskReceipts(eventId: number, receipts: BadgeReceipt[]) {
  return staffRequest<ReceiptResult>(`/admin/events/${eventId}/badges/print-receipts`, { method: "POST", body: JSON.stringify({ receipts }) });
}

/** The design a badge prints on: its role's design, else the attendee one, else the first published. */
export function designFor(bundle: DeskBundle, role: string): { key: string; design: DeskDesign } | null {
  const key = [bundle.roles[role], bundle.roles.attendee, Object.keys(bundle.designs)[0]].find((k) => k && bundle.designs[k]);
  return key ? { key, design: bundle.designs[key] } : null;
}

/** Merge values for every tag a badge prints; answers arrive keyed `field:<key>` already. */
export function badgeValues(badge: DeskBadge): Record<string, string> {
  return { name: badge.name, team: badge.team, role: badge.role_label, crew_kind: badge.crew_kind, email: badge.email ?? "", ...badge.answers };
}

// Version history, "Preview as" holders, exact previews and the calibration sheet for one
// design. Typed by hand (the generated client is not edited by feature lanes).
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { staffRequest, staffRequestBlob } from "../../lib/api";
import type { CardDesign, CardDocument } from "./cardTypes";

const base = (id: number) => `/admin/card-designs/${id}`;

export type ReviewState = "pending" | "approved" | "rejected" | "withdrawn" | "";
export type CardRevision = { revision: number; created_at: string; created_by: string; is_current: boolean;
  is_published: boolean; review: ReviewState; layers: number };
export type CardRevisionDetail = CardRevision & { document: CardDocument };
export type RevisionPage = { count: number; next: string | null; previous: string | null; results: CardRevision[] };
export type CardHolder = { id: number; kind: string; name: string; number: string; label: string; pii_masked?: boolean;
  /** Does this holder have a ready cut-out of their current photo, and did they choose it? */ cutout?: { available: boolean; use_cutout: boolean } };
export type CalibrationPaper = "a4" | "letter" | "card";

export const REVISIONS_PAGE_SIZE = 24;
export const revisionsKey = (id: number) => ["card-design-revisions", id] as const;

export function useRevisions(id: number, page: number) {
  return useQuery({ queryKey: [...revisionsKey(id), page], placeholderData: keepPreviousData,
    queryFn: () => staffRequest<RevisionPage>(`${base(id)}/revisions?page=${page}`) });
}

export function useRevision(id: number, revision: number | null) {
  return useQuery({ queryKey: [...revisionsKey(id), "detail", revision], enabled: revision !== null, staleTime: Infinity,
    queryFn: () => staffRequest<CardRevisionDetail>(`${base(id)}/revisions/${revision}`) });
}

/** Restore `revision` as a new draft. `current` is the design's revision now (compare-and-swap; 409 if it moved). */
export function restoreRevision(id: number, revision: number, current: number) {
  return staffRequest<CardDesign>(`${base(id)}/revisions/${revision}/restore`, {
    method: "POST", body: JSON.stringify({ revision: current }),
  });
}

export function useHolders(id: number, enabled = true) {
  return useQuery({ queryKey: ["card-design-holders", id], enabled, staleTime: 60_000,
    queryFn: () => staffRequest<CardHolder[]>(`${base(id)}/holders`) });
}

const CUTOUT_ROUTE: Record<string, string> = { member_card: "member-cards", staff_card: "staff-cards", event_card: "event-id-cards" };

/** The previewed holder's ready cut-out as a short-lived private link, from the existing photo-cutout status route
 *  (same staff authority as the card; null while none is ready). Fetched whatever the holder chose: a `cutout`
 *  layer prints it regardless, an `auto` layer only when they chose it (photoVariant.pickPhoto decides). */
export function useHolderCutout(holder: CardHolder | null) {
  const route = holder ? CUTOUT_ROUTE[holder.kind] : undefined;
  const wanted = Boolean(holder && route && holder.cutout?.available);
  return useQuery({ queryKey: ["card-holder-cutout", holder?.kind, holder?.id], enabled: wanted, staleTime: 60_000, retry: false,
    queryFn: async () => (await staffRequest<{ image_url: string }>(`/admin/${route}/${holder!.id}/photo-cutout`)).image_url || null });
}

/** A server render of the unsaved document. `bleedMm`/`cropMarks` give the print-ready proof (mirror bleed, crop
 *  marks, PDF trim/bleed boxes); `dpi` is the PNG resolution (150 or 300). */
export function exactPreview(id: number, document: CardDocument, side: "front" | "back",
  options: { format: "png" | "pdf"; longNames: boolean; holderId?: number | null; bleedMm?: number; cropMarks?: boolean; dpi?: 150 | 300 }) {
  return staffRequestBlob(`${base(id)}/preview`, {
    method: "POST", body: JSON.stringify({ document, side, format: options.format, long_names: options.longNames,
      ...(options.holderId ? { holder_id: options.holderId } : {}),
      ...(options.bleedMm ? { bleed_mm: options.bleedMm } : {}), ...(options.cropMarks ? { crop_marks: true } : {}),
      ...(options.dpi ? { dpi: options.dpi } : {}) }),
  });
}

export function calibrationSheet(id: number, paper: CalibrationPaper) {
  return staffRequestBlob(`${base(id)}/calibration?paper=${paper}`);
}

/** Hand a blob to the browser as a download. */
export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(window.document.createElement("a"), { href: url, download: name });
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

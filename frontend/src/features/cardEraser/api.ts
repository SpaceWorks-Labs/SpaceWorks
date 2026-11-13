// Decision 314(c): the background-eraser adapter for card photos. Provider settings (platform and per space),
// the cut-out status of one holder's photo, and the bulk photo upload matched by file name.
import { t } from "@lingui/core/macro";

import { memberRequest, staffRequest } from "../../lib/api";

export type ProviderStatus = {
  configured: boolean; provider_url: string; fingerprint: string;
  last_test_at: string | null; last_test_ok: boolean | null; last_test_error: string;
  use_platform_provider?: boolean; platform_available?: boolean; effective?: "space" | "platform" | null;
};
export type ProviderInput = Partial<{ provider_url: string; secret: string; clear: boolean; use_platform_provider: boolean }>;
export type ProviderScope = { kind: "space"; makerspaceId: number } | { kind: "platform" };
export type TestResult = { ok: boolean; error: string; tested_at: string };

const providerPath = (scope: ProviderScope) => scope.kind === "space"
  ? `/admin/makerspaces/${scope.makerspaceId}/image-adapter` : "/admin/platform/image-adapter";

export const providerKeys = { scope: (scope: ProviderScope) => ["image-adapter", scope.kind === "space" ? scope.makerspaceId : "platform"] as const };

export const providerApi = {
  read: (scope: ProviderScope) => staffRequest<ProviderStatus>(providerPath(scope)),
  save: (scope: ProviderScope, input: ProviderInput) =>
    staffRequest<ProviderStatus>(providerPath(scope), { method: "PATCH", body: JSON.stringify(input) }),
  test: (scope: ProviderScope) => staffRequest<TestResult>(`${providerPath(scope)}/test`, { method: "POST" }),
};

/** What went wrong, in words: the typed error codes the server and a provider can answer with. */
export function eraserErrorText(code: string): string {
  switch (code) {
    case "invalid_signature": return t`The service rejected our signature. Check that the shared secret matches.`;
    case "stale_timestamp": return t`The service says the clocks differ too much. Check both servers' time.`;
    case "provider_unreachable": return t`The service could not be reached.`;
    case "provider_timeout": return t`The service took too long to answer.`;
    case "url_not_allowed": return t`That address is not allowed.`;
    case "no_subject_found": return t`The service found no person in the photo.`;
    case "rate_limited": case "unavailable": return t`The service is busy. It will be tried again.`;
    case "unreadable_image": case "input_not_allowed": return t`The photo could not be used.`;
    case "response_no_alpha": case "response_empty": case "response_not_png": case "response_shape_mismatch":
    case "response_too_large": case "invalid_response": return t`The service sent an answer we can't use.`;
    case "not_configured": return t`No eraser service is set up.`;
    case "photo_missing": return t`The photo is gone.`;
    case "eraser_limit_reached": return t`Photo added. The monthly limit for background removal is reached, so its background was kept.`;
    case "eraser_off": return t`Photo added. Background removal is switched off, so its background was kept.`;
    case "eraser_not_configured": return t`Photo added. No eraser service is set up, so its background was kept.`;
    case "eraser_opted_out": return t`Photo added. This member opted out of background removal, so its background was kept.`;
    default: return code ? t`The background could not be removed.` : "";
  }
}

export type CutoutState = "none" | "queued" | "running" | "done" | "failed" | "stale";
export type Cutout = { available: boolean; state: CutoutState; error_code: string; use: "cutout" | "original";
  image_url: string; width: number; height: number; requested_at: string | null;
  /** Decision 345(b): the space's processing notice, its version, and whether the photo's owner opted out. */
  notice?: string; notice_version?: string; opted_out?: boolean };
export type CutoutTarget = { scope: "staff"; photoPath: string } | { scope: "member"; cardPath: string };

const cutoutPath = (target: CutoutTarget) => target.scope === "staff" ? `${target.photoPath}-cutout` : `${target.cardPath}/photo/cutout`;
const send = <T,>(target: CutoutTarget, path: string, init?: RequestInit) =>
  (target.scope === "staff" ? staffRequest<T>(path, init) : memberRequest<T>(path, init));

export const cutoutKeys = { one: (target: CutoutTarget) => ["card-cutout", cutoutPath(target)] as const };

export const cutoutApi = {
  read: (target: CutoutTarget) => send<Cutout>(target, cutoutPath(target)),
  queue: (target: CutoutTarget, consent: boolean) =>
    send<Cutout>(target, cutoutPath(target), { method: "POST", body: JSON.stringify({ consent }) }),
  choose: (target: CutoutTarget, use: "cutout" | "original") =>
    send<Cutout>(target, cutoutPath(target), { method: "PATCH", body: JSON.stringify({ use }) }),
  discard: (target: CutoutTarget) => send<Cutout>(target, cutoutPath(target), { method: "DELETE" }),
  /** Members only: opt the photo out of (or back into) background removal. */
  optOut: (target: CutoutTarget, opted_out: boolean) =>
    send<Cutout>(target, cutoutPath(target), { method: "PUT", body: JSON.stringify({ opted_out }) }),
};

export type BatchKind = "member_card" | "staff_card" | "event_card";
export type Candidate = { id: number; name: string; number: string };
export type BatchItem = { id: number; filename: string; status: "matched" | "ambiguous" | "unmatched" | "has_photo";
  match_kind: string; holder_id: number | null; holder_name: string; candidates: Candidate[];
  decision: "apply" | "replace" | "keep" | "skip"; state: string; error_code: string; thumbnail_url: string };
export type Batch = { id: number; kind: BatchKind; event_id: number | null; state: "draft" | "applying" | "done" | "cancelled";
  remove_backgrounds: boolean; eraser_available: boolean; file_count: number; applied_count: number; skipped_count: number;
  failed_count: number; expires_at: string; items: BatchItem[]; holders: Candidate[] };

const batches = (makerspaceId: number) => `/admin/makerspaces/${makerspaceId}/card-photo-batches`;
/** Photos per request: keeps each upload small; the server caps a batch at 500. */
export const UPLOAD_CHUNK = 20;
export const UPLOAD_CHUNK_BYTES = 24 * 1024 * 1024;

export const batchApi = {
  create: (makerspaceId: number, body: { kind: BatchKind; event_id?: number | null; holders_consented: boolean; remove_backgrounds: boolean }) =>
    staffRequest<Batch>(batches(makerspaceId), { method: "POST", body: JSON.stringify(body) }),
  read: (makerspaceId: number, id: number) => staffRequest<Batch>(`${batches(makerspaceId)}/${id}`),
  addFiles: (makerspaceId: number, id: number, files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return staffRequest<Batch>(`${batches(makerspaceId)}/${id}/files`, { method: "POST", body: form });
  },
  choose: (makerspaceId: number, id: number, item: number, body: { holder_id?: number | null; decision?: BatchItem["decision"] }) =>
    staffRequest<Batch>(`${batches(makerspaceId)}/${id}/items/${item}`, { method: "PATCH", body: JSON.stringify(body) }),
  apply: (makerspaceId: number, id: number, removeBackgrounds?: boolean) =>
    staffRequest<Batch>(`${batches(makerspaceId)}/${id}/apply`, { method: "POST", body: JSON.stringify(removeBackgrounds === undefined ? {} : { remove_backgrounds: removeBackgrounds }) }),
  cancel: (makerspaceId: number, id: number) => staffRequest<Batch>(`${batches(makerspaceId)}/${id}`, { method: "DELETE" }),
};

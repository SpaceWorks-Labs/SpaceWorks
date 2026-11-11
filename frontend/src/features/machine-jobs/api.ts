import { t } from "@lingui/core/macro";
import { memberRequest, StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { uploadToStorage, type PrintUpload } from "../printing/publicApi";
import type { JobQuote, JobSubmitBody, JobType, MemberJob } from "./types";

const space = (slug: string) => `/public/${encodeURIComponent(slug)}/machine-jobs`;

export const jobKeys = {
  types: (slug: string) => ["public-machine-job-types", slug] as const,
  mine: (makerspaceId?: number) => ["member", "machine-jobs", makerspaceId ?? "all"] as const,
  all: ["member", "machine-jobs"] as const,
  detail: (id: number) => ["member", "machine-job", id] as const,
};

export function fetchJobTypes(slug: string) {
  return tenantPublicRequest<JobType[]>(slug, `${space(slug)}/types`);
}

type StagedFile = { file_id: number; upload: PrintUpload; group: string; max_bytes: number; preview: string };

/** Stage one file against the type's formats, then send the bytes to storage (presigned POST or PUT). */
export async function stageJobFile(slug: string, queueId: number, file: File, kind: "model" | "screenshot") {
  const staged = await tenantPublicRequest<StagedFile>(slug, `${space(slug)}/uploads`, { method: "POST",
    body: JSON.stringify({ queue_id: queueId, filename: file.name, content_type: file.type || "application/octet-stream", kind }) });
  if (staged.max_bytes && file.size > staged.max_bytes) {
    throw new Error(t`${file.name} is larger than the ${Math.floor(staged.max_bytes / 1_048_576)} MB this machine accepts.`);
  }
  await uploadToStorage({ ...staged.upload, fields: staged.upload.fields ?? {} }, file);
  return staged.file_id;
}

export function submitJob(slug: string, body: JobSubmitBody) {
  return tenantPublicRequest<{ id: number; public_token: string; status: string }>(slug, space(slug),
    { method: "POST", body: JSON.stringify(body) });
}

export function fetchMyJobs(makerspaceId?: number) {
  return memberRequest<MemberJob[]>(`/member/machine-jobs${makerspaceId != null ? `?makerspace=${makerspaceId}` : ""}`);
}

export function fetchMyJob(id: number) {
  return memberRequest<MemberJob>(`/member/machine-jobs/${id}`);
}

const post = <T>(path: string, body?: unknown) =>
  memberRequest<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const approveQuote = (id: number, digest: string) => post<MemberJob>(`/member/machine-jobs/${id}/approve-quote`, { digest });
export const declineQuote = (id: number) => post<MemberJob>(`/member/machine-jobs/${id}/decline-quote`);
export const resubmitJob = (id: number, note: string, fileIds: number[]) =>
  post<MemberJob>(`/member/machine-jobs/${id}/resubmit`, { note, file_ids: fileIds });

/** The new quote a 409 `price_changed` carries, normalised to the member shape. */
export function changedQuote(error: unknown): JobQuote | null {
  if (!(error instanceof StructuredApiError) || error.code !== "price_changed") return null;
  const quote = (error.body as { quote?: Partial<JobQuote> | null }).quote;
  if (!quote?.digest) return null;
  return { total: String(quote.total ?? ""), currency: String(quote.currency ?? ""), digest: quote.digest,
    lines: (quote.lines ?? []).map(line => ({ label: String(line.label ?? ""), net: String(line.net ?? "") })) };
}

const SUBMIT_COPY: Record<string, string> = {
  membership_required: t`Job requests are for members of this space. Join or renew your membership first.`,
  presence_required: t`Check in at the space first, then send your request.`,
  waiver_acceptance_required: t`Accept the space's current waiver in your member area, then try again.`,
  job_limit_reached: t`You already have as many open jobs on this machine type as the space allows. Wait for one to finish or cancel one.`,
  type_closed: t`This machine type has stopped taking requests. Choose another type.`,
  capability_disabled: t`This space isn't taking job requests right now.`,
};

/** Clear copy for the refusals a member can act on; anything else keeps the server's message. */
export function jobErrorMessage(error: unknown): string {
  if (error instanceof StructuredApiError) {
    if (error.status === 401) return t`Sign in to your member account to request a job.`;
    if (error.code && SUBMIT_COPY[error.code]) return SUBMIT_COPY[error.code];
    // The server answers the typed switch-off for `machines.job_requests` (decision 221e).
    if (error.code === "feature_disabled" && (error.body as { feature?: unknown }).feature === "machines.job_requests") {
      return SUBMIT_COPY.capability_disabled;
    }
    // A refused file answers {file, code}; the code is for machines, the sentence is for people.
    const field = Object.entries(error.body).find(([key, value]) => key !== "code" && typeof value === "string");
    if (!error.detail && field) return field[1] as string;
  }
  return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
}

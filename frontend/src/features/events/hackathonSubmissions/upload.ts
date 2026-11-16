import { t } from "@lingui/core/macro";
import { memberRequest } from "../../../lib/api";
import { teamBase } from "./api";
import type { Asset, SubmissionScope, UploadDescriptor, UploadResult, UploadSpec } from "./types";

type Resume = { assetId: number; generation: number; version: number; fingerprint: string; operationId: string; completeOperationId: string };
const sessions = new Map<string, Resume>();
export function clearUploadSessions() { sessions.clear(); }
const key = (scope: SubmissionScope) => `sw-event-upload:${scope.accountId}:${scope.makerspaceId}:${scope.eventId}:${scope.teamId}`;

export async function fingerprint(file: File) {
  const head = new Uint8Array(await file.slice(0, 65536).arrayBuffer());
  const tail = new Uint8Array(await file.slice(Math.max(0, file.size - 65536)).arrayBuffer());
  const bytes = new Uint8Array(head.length + tail.length + 16);
  bytes.set(head); bytes.set(tail, head.length);
  new DataView(bytes.buffer).setFloat64(bytes.length - 16, file.size);
  new DataView(bytes.buffer).setFloat64(bytes.length - 8, file.lastModified);
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(n => n.toString(16).padStart(2, "0")).join("");
}

function allowedUploadUrl(url: string, allowedOrigins: readonly string[]) {
  const parsed = new URL(url);
  if (!allowedOrigins.includes(parsed.origin) || !["http:", "https:"].includes(parsed.protocol)
    || parsed.username || parsed.password) throw new Error(t`The upload destination is unavailable.`);
  return url;
}

async function sendFile(file: File, descriptor: UploadDescriptor, record: Resume, scope: SubmissionScope,
  allowedOrigins: readonly string[], signal: AbortSignal, progress: (bytes: number) => void) {
  if (descriptor.method === "POST") {
    if (!descriptor.url || !descriptor.fields) throw new Error(t`Invalid upload configuration.`);
    const body = new FormData();
    for (const [name, value] of Object.entries(descriptor.fields)) body.append(name, value);
    body.append("file", file);
    const response = await fetch(allowedUploadUrl(descriptor.url, allowedOrigins), {
      method: "POST", body, signal, credentials: "omit", cache: "no-store", redirect: "error" });
    if (!response.ok) throw new Error(t`Upload interrupted. Select the same file to retry.`);
    progress(file.size);
    return;
  }
  if (typeof descriptor.part_size !== "number" || !Number.isSafeInteger(descriptor.part_size) || descriptor.part_size < 5 * 1024 ** 2
    || descriptor.part_count !== Math.ceil(file.size / descriptor.part_size) || descriptor.part_count > 10000) {
    throw new Error(t`Invalid upload configuration.`);
  }
  for (let number = 1; number <= descriptor.part_count; number++) {
    signal.throwIfAborted();
    const result = await memberRequest<{ parts: { part_number: number; size_bytes: number; url: string }[] }>(
      `${teamBase(scope)}assets/${record.assetId}/parts/`, { method: "POST", signal,
        body: JSON.stringify({ operation_id: crypto.randomUUID(), expected_version: record.version,
          generation: record.generation, part_numbers: [number] }) });
    const part = result.parts[0];
    const start = (number - 1) * descriptor.part_size;
    const body = file.slice(start, Math.min(start + descriptor.part_size, file.size));
    if (result.parts.length !== 1 || part.part_number !== number || part.size_bytes !== body.size) throw new Error(t`Invalid upload part.`);
    const response = await fetch(allowedUploadUrl(part.url, allowedOrigins), {
      method: "PUT", body, signal, credentials: "omit", cache: "no-store", redirect: "error" });
    if (!response.ok) throw new Error(t`Upload interrupted. Select the same file to resume.`);
    progress(Math.min(number * descriptor.part_size, file.size));
  }
}

export async function uploadProjectFile({ file, spec, scope, allowedOrigins, signal, progress }: {
  file: File; spec: UploadSpec; scope: SubmissionScope; allowedOrigins: readonly string[];
  signal: AbortSignal; progress: (bytes: number) => void;
}): Promise<Asset> {
  if (!file.size || file.size > 2 * 1024 ** 3) throw new Error(t`Choose a nonempty file within the upload limit.`);
  const hash = await fingerprint(file);
  const previous = sessions.get(key(scope)) ?? null;
  if (previous && previous.fingerprint !== hash) throw new Error(t`Select the original file to resume this upload.`);
  let record: Resume;
  let descriptor: UploadDescriptor;
  if (previous && previous.assetId) {
    record = previous;
    const status = await memberRequest<Asset>(`${teamBase(scope)}assets/${record.assetId}/`, { signal });
    if (status.state !== "uploading") {
      if (["ready", "uploaded", "validating", "promoting"].includes(status.state)) {
        sessions.delete(key(scope));
        return status;
      }
      throw new Error(t`This upload has ended. Remove it from your draft before starting a replacement.`);
    }
    descriptor = await memberRequest<UploadDescriptor>(`${teamBase(scope)}assets/${record.assetId}/resume/`, {
      method: "POST", signal, body: JSON.stringify({ operation_id: crypto.randomUUID(),
        expected_version: record.version, generation: record.generation }) });
  } else {
    const operationId = previous?.operationId ?? crypto.randomUUID();
    record = previous ?? { assetId: 0, version: 1, generation: 1, fingerprint: hash, operationId, completeOperationId: crypto.randomUUID() };
    sessions.set(key(scope), record);
    const result = await memberRequest<UploadResult>(`${teamBase(scope)}assets/`, { method: "POST", signal,
      headers: { "Idempotency-Key": operationId }, body: JSON.stringify({ filename: file.name,
        mime: file.type || "application/octet-stream", bytes: file.size, ...spec }) });
    if (!result.upload) throw new Error(t`The upload could not be started.`);
    descriptor = result.upload;
    record = { ...record, assetId: result.asset_id, version: result.version, generation: result.generation };
    sessions.set(key(scope), record);
  }
  await sendFile(file, descriptor, record, scope, allowedOrigins, signal, progress);
  const result = await memberRequest<Asset>(`${teamBase(scope)}assets/${record.assetId}/complete/`, {
    method: "POST", signal, body: JSON.stringify({ operation_id: record.completeOperationId,
      expected_version: record.version, generation: record.generation }) });
  sessions.delete(key(scope));
  return result;
}

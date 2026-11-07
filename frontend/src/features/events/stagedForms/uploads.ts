import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { memberRequest } from "../../../lib/api";
import type { FileReference } from "../../forms/types";
import type { UploadFormFiles } from "../../forms/FileInput";

export type UploadAsset = { asset_id: number; version: number; generation: number; sha256: string;
  state: "initiated" | "uploaded" | "validating" | "ready" | "attached" | "failed" | "expired" | "deleted";
  upload?: { method: "POST"; url: string; fields: Record<string, string>; expires_at: string } };
type StageBinding = { response_id: number; expected_response_version: number; form_revision_id: number };
type VirtualBinding = { creation_operation_id: string; form_revision_id: number };
type Binding = (StageBinding & { question_id: string }) | { claim_uuid: string } |
  { creation_operation_id: string; form_revision_id: number; question_id: string };
export async function uploadPrivateFile(path: string, file: File, binding: Binding, signal: AbortSignal): Promise<FileReference> {
  if (!file.size || file.size > 10485760) throw new Error(t`Invalid file size`);
  const create = crypto.randomUUID();
  const asset = await memberRequest<UploadAsset>(path, { method: "POST", cache: "no-store", signal,
    headers: { "Idempotency-Key": create }, body: JSON.stringify({ operation_id: create, expected_version: 0,
      ...binding, original_filename: file.name, declared_mime: file.type || "application/octet-stream", expected_bytes: file.size }) });
  if (!asset.upload || asset.upload.method !== "POST" || Date.parse(asset.upload.expires_at) <= Date.now()) throw new Error(t`Upload unavailable`);
  const body = new FormData();
  Object.entries(asset.upload.fields).forEach(([key, value]) => body.append(key, value)); body.append("file", file);
  const stored = await fetch(asset.upload.url, { method: "POST", body, signal, credentials: "omit", referrerPolicy: "no-referrer" });
  if (!stored.ok) throw new Error(t`Upload unavailable`);
  const operation = crypto.randomUUID();
  let current = await memberRequest<UploadAsset>(`${path}${asset.asset_id}/complete/`, {
    method: "POST", cache: "no-store", signal, headers: { "Idempotency-Key": operation },
    body: JSON.stringify({ operation_id: operation, expected_version: asset.version, generation: asset.generation }) });
  for (let attempt = 0; attempt < 30; attempt++) {
    if (["ready", "attached"].includes(current.state)) {
      if (!Number.isSafeInteger(current.asset_id) || current.asset_id < 1 || !Number.isSafeInteger(current.generation) || current.generation < 1 || !/^[a-f0-9]{64}$/.test(current.sha256)) throw new Error(t`Invalid upload reference`);
      return { asset_id: current.asset_id, generation: current.generation, sha256: current.sha256 };
    }
    if (["failed", "expired", "deleted"].includes(current.state)) throw new Error(t`File unavailable`);
    await new Promise<void>((resolve, reject) => {
      const abort = () => { clearTimeout(timer); reject(new Error(t`Upload cancelled`)); };
      const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, 1000);
      if (signal.aborted) abort(); else signal.addEventListener("abort", abort, { once: true });
    });
    current = await memberRequest<UploadAsset>(`${path}${asset.asset_id}/`, { cache: "no-store", signal });
  }
  throw new Error(t`File checks are still pending. Retry later.`);
}
export function useFormUploads(path: string, binding: StageBinding | VirtualBinding | { claim_uuid: string }) {
  const controllers = useRef(new Set<AbortController>());
  const [busy, setBusy] = useState(false);
  useEffect(() => () => { controllers.current.forEach(controller => controller.abort()); }, [path]);
  const upload: UploadFormFiles = async (question, files) => {
    const controller = new AbortController(); controllers.current.add(controller); setBusy(true);
    try {
      const refs = [];
      for (const file of files) refs.push(await uploadPrivateFile(path, file,
        "claim_uuid" in binding ? binding : { ...binding, question_id: question.id }, controller.signal));
      return refs;
    } finally { controllers.current.delete(controller); if (!controller.signal.aborted) setBusy(controllers.current.size > 0); }
  };
  return { upload, busy };
}

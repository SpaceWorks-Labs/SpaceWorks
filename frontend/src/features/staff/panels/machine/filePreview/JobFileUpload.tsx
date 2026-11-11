// Staff attach a file to a job (machine staff, `manage_machines` in the machine's scope): stage
// it against the machine's file policy (presign), send the bytes straight to private storage
// with the same helper the public upload uses, then finalize. A staged file that never
// finalizes is deleted so it does not hold storage.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorText } from "../../../../../components/ui";
import { staffRequest } from "../../../../../lib/api";
import { uploadToStorage, type PrintUpload } from "../../../../printing/publicApi";

const base = "/admin/machine-service";

export async function uploadJobFile(requestId: number, file: File) {
  const staged = await staffRequest<{ file_id: number; upload: PrintUpload }>(`${base}/requests/${requestId}/files/presign`, {
    method: "POST", body: JSON.stringify({ filename: file.name, content_type: file.type || "application/octet-stream" }) });
  try {
    await uploadToStorage({ ...staged.upload, fields: staged.upload.fields ?? {} }, file);
    return await staffRequest<{ file_id: number }>(`${base}/requests/${requestId}/files/finalize`, {
      method: "POST", body: JSON.stringify({ file_id: staged.file_id }) });
  } catch (error) {
    await staffRequest<void>(`${base}/files/${staged.file_id}`, { method: "DELETE" }).catch(() => undefined);
    throw error;
  }
}

export function JobFileUpload({ requestId, onUploaded }: { requestId: number; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setError(""); setDone("");
    try {
      await uploadJobFile(requestId, file);
      setDone(t`${file.name} added.`);
      onUploaded();
    } catch (failure) {
      setError(failure instanceof Error && failure.message ? failure.message : t`The file could not be added. Try again.`);
    } finally { setBusy(false); }
  };
  return <div className="grid gap-2 rounded-xl border border-dashed border-line p-3">
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Add a file`}
      <input type="file" className="desk-input min-h-11" disabled={busy}
        onChange={event => { void upload(event.target.files?.[0]); event.target.value = ""; }} /></label>
    <p className="text-sm text-muted">{busy ? t`Uploading…` : t`Accepted formats and size follow this machine's file settings.`}</p>
    {done ? <p role="status" className="text-sm text-success-ink">{done}</p> : null}
    {error ? <ErrorText message={error} /> : null}
  </div>;
}

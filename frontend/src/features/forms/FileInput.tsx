import { useEffect, useRef, useState } from "react";
import { Paperclip, X } from "lucide-react";
import type { CompoundInputProps, FileReference } from "./types";

export type UploadFormFiles = (question: CompoundInputProps["question"], files: File[]) => Promise<FileReference[]>;
export function FileInput({ question: q, value, onChange, invalid, describedBy, upload }: CompoundInputProps & { upload?: UploadFormFiles }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const references = Array.isArray(value) ? value as FileReference[] : [];
  const config = q.file;
  return <div className="grid gap-2" aria-busy={busy}>
    <label className="grid gap-1 text-sm">{q.label} files
      <input className="desk-input" type="file" multiple={(config?.max_files ?? 1) > 1} disabled={!upload || busy || references.length >= (config?.max_files ?? 1)}
        required={q.required && !references.length} aria-invalid={invalid || Boolean(error) || undefined} aria-describedby={`${describedBy ?? ""} file-${q.id}-status`.trim()}
        onChange={async e => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          if (!files.length || !upload || !config || pending.current) return;
          if (files.length + references.length > config.max_files || files.some(file => file.size > config.max_bytes_each || !file.size)) {
            setError(`Choose up to ${config.max_files} nonempty files, each at most ${config.max_bytes_each} bytes.`); return;
          }
          setError(""); setBusy(true); pending.current = true;
          try {
            const ready = await upload(q, files);
            if (ready.length !== files.length || ready.some(ref => !Number.isSafeInteger(ref.asset_id) || ref.asset_id < 1 || !Number.isSafeInteger(ref.generation) || ref.generation < 1 || !/^[a-f0-9]{64}$/.test(ref.sha256))
                || new Set([...references, ...ready].map(ref => ref.asset_id)).size !== references.length + ready.length) throw new Error("unavailable");
            if (active.current) onChange([...references, ...ready]);
          } catch { if (active.current) setError("Couldn’t upload the files. Choose them again to retry."); }
          finally { pending.current = false; if (active.current) setBusy(false); }
        }} />
    </label>
    <p id={`file-${q.id}-status`} role="status" className="text-sm text-muted">{busy ? "Uploading and checking files…" : upload ? `${references.length} of ${config?.max_files ?? 1} files attached.` : "File upload is unavailable in this form context."}</p>
    {references.map((ref, index) => <div key={ref.asset_id} className="flex items-center gap-2 text-sm"><Paperclip size={20} aria-hidden="true" />File {index + 1}<button type="button" className="desk-button" disabled={busy} aria-label={`Remove file ${index + 1}`} onClick={() => onChange(references.filter(item => item.asset_id !== ref.asset_id))}><X size={20} aria-hidden="true" /></button></div>)}
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
  </div>;
}

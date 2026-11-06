import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Download } from "lucide-react";

import { ErrorText, Modal } from "../../../../../components/ui";
import type { ServiceFile } from "../../../../../generated/api";
import { staffRequest } from "../../../../../lib/api";
import { JobFilePreview } from "./JobFilePreview";

const signedUrl = (fileId: number) => staffRequest<{ url: string }>(`/admin/machine-service/files/${fileId}/url`);

/** Fetch the bytes behind a private, short-lived signed URL; no cookies or referrer go to storage. */
export async function loadJobFile(fileId: number, signal: AbortSignal) {
  const { url } = await signedUrl(fileId);
  const response = await fetch(url, { signal, credentials: "omit", referrerPolicy: "no-referrer" });
  if (!response.ok) throw new Error(t`The file could not be loaded.`);
  return response.blob();
}

const size = (bytes: number) => bytes >= 1024 ** 2 ? `${(bytes / 1024 ** 2).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

/** A job's files for staff review: download each, and preview the safe formats in the browser. */
export function JobFilesDialog({ title, files, onClose }: { title: string; files: ServiceFile[]; onClose: () => void }) {
  const [error, setError] = useState("");
  const download = async (fileId: number) => {
    setError("");
    try {
      const { url } = await signedUrl(fileId);
      const link = document.createElement("a");
      link.href = url; link.rel = "noopener noreferrer"; link.target = "_blank"; link.click();
    } catch { setError(t`Couldn't get the file. Try again.`); }
  };
  return <Modal open size="xl" title={t`Files: ${title}`} onClose={onClose}>
    <ul className="grid gap-4" aria-label={t`Job files`}>
      {files.map(file => <li key={file.id} className="grid gap-3 rounded-xl border border-line bg-surface p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="min-w-0 [overflow-wrap:anywhere]"><span className="font-semibold text-ink">{file.original_filename}</span>
            <span className="text-sm text-muted"> · {file.kind === "screenshot" ? t`Screenshot` : t`Design file`} · {size(file.size_bytes)}</span></span>
          <button type="button" className="desk-button min-h-11 gap-2" onClick={() => { void download(file.id); }}>
            <Download aria-hidden="true" size={18} />{t`Download`}</button>
        </div>
        <JobFilePreview fileId={file.id} filename={file.original_filename} bytes={file.size_bytes}
          load={signal => loadJobFile(file.id, signal)} />
      </li>)}
    </ul>
    {error ? <ErrorText message={error} /> : null}
  </Modal>;
}

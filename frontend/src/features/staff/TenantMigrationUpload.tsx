import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  completeImportUpload, getImport, startImportUpload, tenantMigrationKeys,
  uploadImportChunk, type ImportJob,
} from "./tenantMigrationApi";
import { StructuredApiError } from "../../lib/api";
import { ErrorText } from "./tenantMigrationUi";

const CHUNK_BYTES = 8 * 1024 * 1024;
const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function validateFile(job: ImportJob, file: File) {
  if (file.size !== job.upload_total_bytes) {
    throw new Error("Choose the original archive: its size must match this upload session.");
  }
  if (!Number.isSafeInteger(job.upload_received_bytes)
    || job.upload_received_bytes < 0 || job.upload_received_bytes > file.size) {
    throw new Error("The server returned an invalid upload offset. Refresh the import job.");
  }
}

export async function uploadArchive(
  initialJob: ImportJob, file: File, onProgress: (job: ImportJob) => void,
) {
  let job = initialJob;
  let retries = 0;
  validateFile(job, file);
  while (job.status === "uploading" && job.upload_received_bytes < file.size) {
    const offset = job.upload_received_bytes;
    try {
      job = await uploadImportChunk(job.id, offset, file.slice(offset, offset + CHUNK_BYTES));
      retries = 0;
    } catch (error) {
      if (error instanceof StructuredApiError && error.status === 413) {
        // Retrying cannot help: the proxy in front of the API caps request bodies.
        throw new Error("The web server refused an 8 MiB upload chunk (HTTP 413). Raise its /api/ request-body limit (nginx client_max_body_size) to at least 10m, then resume this upload.");
      }
      // A lost 200 may mean the bytes already committed. Always ask the server
      // before retrying; another tab can also have advanced or completed the job.
      try { job = await getImport(job.id); } catch { /* Retry the bounded chunk if reconciliation is unavailable. */ }
      validateFile(job, file);
      onProgress(job);
      if (job.status !== "uploading" || job.upload_received_bytes > offset) {
        retries = 0;
        continue;
      }
      if (retries === 3) throw error;
      await wait(500 * 2 ** retries++);
      continue;
    }
    validateFile(job, file);
    onProgress(job);
  }
  if (job.status !== "uploading") return job;
  try {
    job = await completeImportUpload(job.id);
  } catch (error) {
    const reconciled = await getImport(job.id);
    onProgress(reconciled);
    if (reconciled.status === "uploading") throw error;
    job = reconciled;
  }
  onProgress(job);
  return job;
}

type UploadInput = { file: File } & (
  { job: ImportJob; sourceArchiveDigest?: never }
  | { job?: never; sourceArchiveDigest: string }
);

// Both create and resume publish server state to the same list/detail caches.
export function useImportArchiveUpload() {
  const client = useQueryClient();
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const publish = (job: ImportJob) => {
    client.setQueryData(tenantMigrationKeys.import(job.id), job);
    client.setQueryData<ImportJob[]>(tenantMigrationKeys.imports, (rows = []) =>
      rows.some((row) => row.id === job.id)
        ? rows.map((row) => row.id === job.id ? job : row)
        : [job, ...rows].slice(0, 20));
  };
  const upload = useMutation({
    mutationFn: async (input: UploadInput) => {
      let job = input.job;
      try {
        job ??= await startImportUpload({
          archive_bytes: input.file.size, source_archive_digest: input.sourceArchiveDigest!,
        });
        setActiveJobId(job.id);
        publish(job); // A failed first chunk must still leave a visible resume card.
        void client.invalidateQueries({ queryKey: tenantMigrationKeys.imports });
        return await uploadArchive(job, input.file, publish);
      } finally {
        setActiveJobId(null);
        await Promise.all([
          client.invalidateQueries({ queryKey: tenantMigrationKeys.imports }),
          ...(job ? [client.invalidateQueries({ queryKey: tenantMigrationKeys.import(job.id) })] : []),
        ]);
      }
    },
  });
  return { upload, activeJobId };
}

export function ImportUploadResume({ job, driving }: { job: ImportJob; driving: boolean }) {
  const [file, setFile] = useState<File | null>(null);
  const { upload } = useImportArchiveUpload();
  const active = driving || upload.isPending;
  const received = job.upload_received_bytes.toLocaleString();
  const total = job.upload_total_bytes?.toLocaleString() ?? "unknown";
  return (
    <div className="mt-3 rounded-md border border-line bg-bg p-3">
      <p className="text-sm text-ink" aria-live="polite">
        {active ? `Uploaded ${received} of ${total} bytes` : `Upload interrupted at ${received} of ${total} bytes — choose the same file to resume.`}
      </p>
      <progress className="mt-2 w-full" aria-label="Archive upload progress" value={job.upload_received_bytes} max={job.upload_total_bytes ?? 1} />
      {!active ? <>
        <label className="mt-2 block text-sm text-ink">Original encrypted archive
          <input className="desk-input mt-1 w-full" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        {file && file.size !== job.upload_total_bytes ? <p className="mt-2 text-sm text-danger" role="alert">The file size differs from the original archive.</p> : null}
        <button className="desk-button-primary mt-3" type="button" disabled={!file || file.size !== job.upload_total_bytes} onClick={() => {
          if (file) upload.mutate({ job, file });
        }}>Resume upload</button>
      </> : null}
      <ErrorText error={upload.error} />
    </div>
  );
}

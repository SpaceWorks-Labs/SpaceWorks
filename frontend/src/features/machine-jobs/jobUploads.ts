import { plural, t } from "@lingui/core/macro";
import { uploadPrintFilesBounded } from "../printing/PublicPrintUploads";
import { jobErrorMessage, stageJobFile } from "./api";

export type JobFile = { file: File; kind: "model" | "screenshot" };
export type FileErrors = Record<string, string>;

export const fileKey = (file: File) => `${file.name}-${file.size}-${file.lastModified}`;

/** Thrown when one or more files failed; `errors` maps each failed file to its own message. */
export class JobUploadError extends Error {
  constructor(readonly errors: FileErrors) {
    super(plural(Object.keys(errors).length, { one: "# file could not be uploaded. Fix or remove it and try again.", other: "# files could not be uploaded. Fix or remove them and try again." }));
  }
}

/**
 * Stage and upload every file, three at a time (the print form's bounded uploader), and keep
 * going past a failure so the member sees every bad file at once rather than one per attempt.
 */
export async function uploadJobFiles(slug: string, queueId: number, files: JobFile[], setProgress: (message: string) => void, available: () => boolean = () => true) {
  const errors: FileErrors = {};
  const ids = await uploadPrintFilesBounded(files.map(item => ({ file: item.file, kind: item.kind === "model" ? "stl" as const : "screenshot" as const })),
    async item => {
      try {
        if (!available()) throw new Error(t`Machine requests unavailable.`);
        return await stageJobFile(slug, queueId, item.file, item.kind === "stl" ? "model" : "screenshot");
      } catch (error) {
        errors[fileKey(item.file)] = jobErrorMessage(error);
        return -1;
      }
    }, setProgress);
  setProgress("");
  if (Object.keys(errors).length) throw new JobUploadError(errors);
  return ids;
}

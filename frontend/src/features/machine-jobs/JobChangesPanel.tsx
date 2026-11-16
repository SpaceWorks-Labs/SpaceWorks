import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { fetchJobTypes, jobErrorMessage, jobKeys, resubmitJob } from "./api";
import { formatError, JobFilesStep } from "./JobFilesStep";
import { JobUploadError, uploadJobFiles, type FileErrors } from "./jobUploads";
import { extensionList } from "./JobTypeStep";
import type { MemberJob } from "./types";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

/**
 * "Needs changes": the staff message, then the member's answer -- a note and, when the files were
 * the problem, new files. New files are staged against the job's type first, exactly as on submit.
 */
export function JobChangesPanel({ job, slug, onUpdated }: { job: MemberJob; slug: string; onUpdated: (job: MemberJob) => void }) {
  const [note, setNote] = useState("");
  const [models, setModels] = useState<File[]>([]);
  const [screenshots, setScreenshots] = useState<File[]>([]);
  const [errors, setErrors] = useState<FileErrors>({});
  const [progress, setProgress] = useState("");
  // The type list gives the job's queue its accepted formats; files are staged against that queue.
  const types = useQuery({ queryKey: jobKeys.types(slug), queryFn: () => fetchJobTypes(slug), enabled: Boolean(slug), retry: false });
  const type = types.data?.find(row => row.queue_id === job.queue_id);
  const send = useMutation({
    mutationFn: async () => {
      const files = [...models.map(file => ({ file, kind: "model" as const })), ...screenshots.map(file => ({ file, kind: "screenshot" as const }))];
      const ids = files.length && type ? await uploadJobFiles(slug, type.queue_id, files, setProgress) : [];
      return resubmitJob(job.id, note.trim(), ids);
    },
    onSuccess: onUpdated,
    onError: error => { if (error instanceof JobUploadError) setErrors(error.errors); },
  });
  if (job.label !== "needs_changes") return null;
  const empty = !note.trim() && !models.length && !screenshots.length;
  const badFile = type ? models.some(file => formatError(file, extensionList(type))) : false;
  return <section className="desk-panel grid gap-4 border-warn p-5" aria-labelledby="job-changes-title">
    <div><h2 id="job-changes-title" className="title-panel">{t`Needs changes`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Staff looked at your job and need something from you before it can go ahead.`}</p></div>
    {job.changes_message ? <blockquote className="whitespace-pre-wrap break-words rounded-control border border-line bg-panel p-3 text-sm text-ink">{job.changes_message}</blockquote> : null}
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (!empty && !badFile) send.mutate(); }}>
      <Field label={t`Your reply`} hint={t`What you changed, or an answer to staff's question.`}>
        <textarea className="desk-input min-h-24 w-full" maxLength={4000} value={note} onChange={event => setNote(event.target.value)} disabled={send.isPending} />
      </Field>
      {type ? <JobFilesStep accepted={extensionList(type)} typeName={type.name} models={models} screenshots={screenshots} errors={errors} disabled={send.isPending} optional
        onChange={next => { if (next.models) setModels(next.models); if (next.screenshots) setScreenshots(next.screenshots); setErrors({}); }} />
        : types.isPending ? <LogoLoader label={t`Loading file options…`} size={48} className="min-h-16 py-3" />
          : <p className="text-sm text-muted">{t`New files can't be added here right now. Reply with a note, or ask staff.`}</p>}
      {progress ? <p className="text-sm text-muted" role="status">{progress}</p> : null}
      {send.isError ? <p className="text-sm text-danger" role="alert">{jobErrorMessage(send.error)}</p> : null}
      <button type="submit" className="desk-button-brand justify-self-start" disabled={empty || badFile || send.isPending}>
        {send.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send changes`}</button>
    </form>
  </section>;
}

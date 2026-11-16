import { t } from "@lingui/core/macro";
import { useState } from "react";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { LogoLoader } from "../../../../../components/LogoLoader";
import { TypeDocuments } from "./TypeDocuments";
import { useSaveTypeSetup, useTypeSetup, type TypeSetup } from "./typeSetupApi";
import type { StepProps } from "./wizardTypes";

type Form = { notes: string; atSession: boolean; atJob: boolean };

function NotesForm({ ctx, setup }: StepProps & { setup: TypeSetup }) {
  const typeId = ctx.machineType!.id;
  const suggestion = ctx.prefill?.documents.training_notes ?? ctx.spec?.documents.training_notes ?? "";
  const fresh = !setup.updated_at && !setup.training_notes;
  const saved: Form = { notes: fresh ? suggestion : setup.training_notes, atSession: setup.notes_at_session_start, atJob: setup.notes_at_job_request };
  const [draft, setDraft] = useState<Form | null>(null);
  const form = draft ?? saved;
  const save = useSaveTypeSetup(ctx.makerspaceId, typeId);
  const set = (patch: Partial<Form>) => { save.reset(); setDraft({ ...form, ...patch }); };
  const dirty = draft !== null || (fresh && suggestion !== "");
  const tooLong = form.notes.length > 10000;
  return <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (!tooLong) save.mutate({ training_notes: form.notes, notes_at_session_start: form.atSession, notes_at_job_request: form.atJob }, { onSuccess: () => setDraft(null) }); }}>
    <p className="text-sm text-muted">{t`Members see these notes on the machine type page, with the documents marked for members.`}</p>
    {fresh && suggestion ? <p className="text-sm text-muted">{t`This is the template's training note. Save to keep it.`}</p> : null}
    <label className="grid gap-1 text-sm">{t`Training notes`}<textarea className="desk-input min-h-32" value={form.notes} onChange={event => set({ notes: event.target.value })} />
      <span className={`text-xs ${tooLong ? "text-danger" : "text-muted"}`}>{`${form.notes.length} / 10000`}</span></label>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.atSession} onChange={event => set({ atSession: event.target.checked })} />{t`Show the notes when a member starts a session`}</label>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.atJob} onChange={event => set({ atJob: event.target.checked })} />{t`Show the notes when a member requests a job`}</label>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    {save.isSuccess && !dirty ? <p role="status" className="text-sm text-success-ink">{t`Training notes saved.`}</p> : null}
    <div><button type="submit" className="desk-button-primary min-h-11" disabled={!dirty || tooLong || save.isPending}>
      {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save training notes`}</button></div>
  </form>;
}

/** Step 11: the type's training notes, where members see them, and its documents. */
export function StepDocuments({ ctx }: StepProps) {
  const type = ctx.machineType!;
  const setup = useTypeSetup(ctx.makerspaceId, type.id);
  return <div className="grid gap-5">
    {setup.isLoading ? <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" /> : null}
    {setup.isError ? <p role="alert" className="text-sm text-danger">{setup.error.message}</p> : null}
    {setup.data ? <NotesForm key={setup.data.updated_at ?? "new"} ctx={ctx} setup={setup.data} /> : null}
    <TypeDocuments makerspaceId={ctx.makerspaceId} typeId={type.id} />
  </div>;
}

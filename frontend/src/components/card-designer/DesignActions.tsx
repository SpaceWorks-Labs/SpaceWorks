// Publish, or submit for approval when this design needs it; approvers approve or send it back.
// Autosave only keeps a draft: cards keep printing the published version until one of these.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { CardDesign } from "./cardTypes";
import { SAVE_STATUS_LABELS, type SaveStatus } from "./useCardDesign";
import { useApproveDesign, usePublishDesign, useRejectDesign, useSubmitDesign } from "./designerApi";

const STATUS_LABELS: Record<CardDesign["status"], string> = {
  draft: t`Draft`, pending_approval: t`Waiting for approval`, published: t`Published`,
};

export function DesignActions({ design, saveStatus, saveError, canEdit, flush, onRetry, onReload }: {
  design: CardDesign; saveStatus: SaveStatus; saveError: string | null; canEdit: boolean;
  flush: () => Promise<void>; onRetry: () => void; onReload: () => void;
}) {
  const publish = usePublishDesign(design.id);
  const submit = useSubmitDesign(design.id);
  const approve = useApproveDesign(design.id);
  const reject = useRejectDesign(design.id);
  const [note, setNote] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const failure = [publish, submit, approve, reject].find((mutation) => mutation.isError)?.error;
  const busy = [publish, submit, approve, reject].some((mutation) => mutation.isPending) || saveStatus === "saving";
  const pending = design.pending_approval;
  const sentBack = !pending && design.last_review?.decision === "rejected" ? design.last_review : null;
  const changed = design.has_unpublished_changes || saveStatus === "pending";

  async function run(action: () => Promise<unknown>) {
    await flush();
    await action().catch(() => undefined);
  }

  return <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1" aria-label={t`Publishing`} role="group">
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="rounded-full border border-line px-2 py-0.5 font-semibold text-ink">{STATUS_LABELS[design.status]}</span>
      <span aria-live="polite" className={saveStatus === "error" || saveStatus === "conflict" ? "text-danger" : "text-muted"}>
        {SAVE_STATUS_LABELS[saveStatus]}</span>
      {design.published_at && !changed ? <span className="hidden text-muted min-[1800px]:inline">{t`Cards use this version.`}</span> : null}
      {design.published_at && changed ? <span className="hidden text-muted min-[1800px]:inline">{t`Cards keep the last published version until you publish.`}</span> : null}
      {!design.published_at ? <span className="hidden text-muted min-[1800px]:inline">{t`Cards use the built-in design until you publish.`}</span> : null}
    </div>
    {saveStatus === "error" ? <p role="alert" className="basis-full text-sm text-danger">{saveError}
      {" "}<button type="button" className="underline" onClick={onRetry}>{t`Try again`}</button></p> : null}
    {saveStatus === "conflict" ? <p role="alert" className="basis-full text-sm text-danger">{t`Someone else saved this design.${" "}`}<button type="button" className="underline" onClick={onReload}>{t`Load their version`}</button> {t` (your unsaved edits are dropped).`}</p> : null}
    {pending ? <p className="basis-full text-sm text-muted">{t`Revision ${pending.revision} was submitted for approval${pending.note ? `: “${pending.note}”` : "."}`}</p> : null}
    {sentBack ? <p className="basis-full text-sm text-warn-ink">{t`Revision ${sentBack.revision} was sent back${sentBack.note ? `: “${sentBack.note}”` : "."}`}</p> : null}
    {failure ? <p role="alert" className="basis-full text-sm text-danger">{failure instanceof Error ? failure.message : t`That didn't work.`}</p> : null}
    <div className="flex flex-wrap gap-2">
      {canEdit && !design.needs_approval ? <button type="button" className="desk-button-primary min-h-11" disabled={busy || saveStatus === "conflict"}
        onClick={() => void run(() => publish.mutateAsync({}))}>{t`Publish`}</button> : null}
      {canEdit && design.needs_approval && !pending ? <button type="button" className="desk-button-primary min-h-11"
        disabled={busy || saveStatus === "conflict"} onClick={() => void run(() => submit.mutateAsync({}))}>{t`Submit for approval`}</button> : null}
      {pending && design.can_approve ? <>
        <button type="button" className="desk-button-success min-h-11" disabled={busy}
          onClick={() => void run(() => approve.mutateAsync({ note: "" }))}>{t`Approve and publish`}</button>
        <button type="button" className="desk-button min-h-11" disabled={busy} aria-expanded={rejecting}
          onClick={() => setRejecting((value) => !value)}>{t`Send back`}</button>
      </> : null}
    </div>
    {rejecting ? <div className="grid gap-2">
      <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`What needs to change`}</span>
        <input className="desk-input min-h-11" maxLength={300} value={note} onChange={(event) => setNote(event.target.value)} /></label>
      <div><button type="button" className="desk-button-danger-outline min-h-11" disabled={busy || note.trim().length < 3}
        onClick={() => void reject.mutateAsync({ note: note.trim() }).then(() => { setRejecting(false); setNote(""); }).catch(() => undefined)}>
        {t`Send back with this note`}</button></div>
    </div> : null}
  </div>;
}

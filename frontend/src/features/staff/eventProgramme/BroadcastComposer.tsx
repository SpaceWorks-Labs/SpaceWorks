import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { Card, ConfirmDialog } from "../../../components/ui";
import { eventErrorText } from "../eventUi";
import { useBroadcastCreate, useBroadcastTemplates, type BroadcastCampaign, type BroadcastDraft, type BroadcastTemplate } from "./broadcastApi";
import { draftComplete, draftStatusText, useDraftAutosave, useDraftDiscard, useUnsavedGuard } from "./broadcastAutosave";
import { BroadcastAudienceFields, BroadcastCtaFields } from "./BroadcastComposerFields";
import { BroadcastToolbar } from "./BroadcastToolbar";
import { isProtectedDenial } from "./sessionScope";
import { BroadcastDesignPicker } from "./BroadcastDesignPicker";
import { BroadcastTemplateGallery } from "./BroadcastTemplateGallery";
import { BoxArt } from "../../../components/BoxSpinner";

export const EMPTY_BROADCAST: BroadcastDraft = { subject: "", body: "", statuses: ["registered", "attended"], attendance: "any", render_schema_version: 2, design: "classic", ctas: [] };
const asDraft = (row: BroadcastCampaign): BroadcastDraft => ({ subject: row.subject, body: row.body, statuses: row.statuses, attendance: row.attendance,
  render_schema_version: 2, design: row.design ?? "classic", ctas: row.ctas ?? [] });
type Pending = { kind: "template"; template: BroadcastTemplate } | { kind: "discard" } | null;

/**
 * The broadcast composer (B21/B22). The draft is private to its author; starting again reopens it. Edits save
 * on their own after a pause, a status line says where the draft stands, and replacing or discarding written
 * work always asks first. Closing the tab with unsaved work asks too.
 */
export function BroadcastComposer({ makerspaceId, eventId, initial, existing, onSaved, onDiscarded }: {
  makerspaceId: number; eventId: number; initial?: BroadcastDraft; existing?: BroadcastCampaign;
  onSaved: (campaign: BroadcastCampaign) => void; onDiscarded?: () => void;
}) {
  const [draft, setDraft] = useState<BroadcastDraft>(initial ?? (existing ? asDraft(existing) : EMPTY_BROADCAST));
  const [saved, setSaved] = useState<BroadcastCampaign | null>(existing ?? null);
  const [pending, setPending] = useState<Pending>(null);
  const body = useRef<HTMLTextAreaElement>(null);
  const create = useBroadcastCreate(makerspaceId, eventId);
  const discard = useDraftDiscard(makerspaceId, eventId);
  const templates = useBroadcastTemplates(makerspaceId, eventId);
  const autosave = useDraftAutosave(makerspaceId, eventId, saved, draft, row => { setSaved(row); onSaved(row); });
  const lastAttempt = useRef({ digest: "", id: "" });
  const denied = isProtectedDenial(create.error) || isProtectedDenial(discard.error);
  const written = !!draft.subject.trim() || !!draft.body.trim();
  const unsaved = saved ? autosave.dirty || autosave.state.saving : written;
  const firstSave = !saved && !create.isPending && !create.isError && draftComplete(draft);
  useUnsavedGuard(unsaved && !denied);
  // The first complete subject and message create the draft (or reopen this author's one); later edits PATCH it.
  useEffect(() => {
    if (!firstSave) return;
    const timer = setTimeout(submit, 2000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstSave, JSON.stringify(draft)]);
  useEffect(() => { if (denied) { setDraft({ ...EMPTY_BROADCAST, statuses: [] }); setSaved(null); lastAttempt.current = { digest: "", id: "" }; } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">{t`Broadcast composition is no longer available for your access.`}</p>;
  const patch = (value: Partial<BroadcastDraft>) => setDraft({ ...draft, ...value });
  const loadTemplate = (template: BroadcastTemplate) => patch({ subject: template.subject, body: template.body, statuses: template.statuses, attendance: template.attendance, design: template.design });
  function submit() {
    if (saved) { autosave.flush(); onSaved(saved); return; }
    const digest = JSON.stringify(draft);
    if (lastAttempt.current.digest !== digest) lastAttempt.current = { digest, id: crypto.randomUUID() };
    create.mutate({ operation_id: lastAttempt.current.id, draft }, { onSuccess: row => { setSaved(row); onSaved(row); } });
  }
  const confirmPending = () => {
    if (pending?.kind === "template") { loadTemplate(pending.template); setPending(null); return; }
    const reset = () => { setDraft(EMPTY_BROADCAST); setSaved(null); setPending(null); create.reset(); lastAttempt.current = { digest: "", id: "" }; onDiscarded?.(); };
    if (saved) discard.mutate(saved.id, { onSuccess: reset, onError: () => setPending(null) }); else reset();
  };
  const status = draftStatusText(autosave.state, saved ? autosave.dirty : written, Boolean(saved));
  return <Card><form className="grid gap-4" onSubmit={e => { e.preventDefault(); submit(); }}>
    <BroadcastTemplateGallery templates={templates} onPick={template => written ? setPending({ kind: "template", template }) : loadTemplate(template)} />
    <label className="grid gap-1 text-sm font-semibold">{t`Subject`}<input className="desk-input font-normal" required maxLength={200} value={draft.subject} onChange={e => patch({ subject: e.target.value })} /></label>
    <div className="grid gap-2">
      <label htmlFor={`broadcast-body-${eventId}`} className="text-sm font-semibold">{t`Message`}</label>
      <BroadcastToolbar field={body} value={draft.body} onChange={value => patch({ body: value })} />
      <textarea ref={body} id={`broadcast-body-${eventId}`} className="desk-input min-h-40 font-normal" required maxLength={10000} value={draft.body} onChange={e => patch({ body: e.target.value })} />
      <p className="text-xs text-muted">{t`Headings, quotes, lists and links are kept; everything else is sent as plain text. Placeholders are filled in for each guest.`}</p>
    </div>
    <BroadcastDesignPicker value={draft.design} extended={!!templates.data} onChange={design => patch({ design })} />
    <BroadcastCtaFields draft={draft} patch={patch} />
    <BroadcastAudienceFields draft={draft} patch={patch} />
    {create.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(create.error)}</p> : null}
    {discard.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(discard.error)}</p> : null}
    <div className="flex flex-col gap-3 border-t border-line pt-3 sm:flex-row sm:items-center">
      <p role="status" aria-live="polite" aria-atomic="true" className={`flex flex-1 flex-wrap items-center gap-x-1.5 text-sm ${autosave.state.conflict || autosave.state.failed ? "text-danger" : "text-muted"}`}>
        <span>{status}</span>
        {autosave.state.failed && autosave.dirty && !autosave.state.conflict ? <><span aria-hidden="true">·</span><button type="button" className="font-semibold text-ink underline underline-offset-4" onClick={autosave.flush}>{t`Retry`}</button></> : null}
      </p>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {saved || written ? <button className="desk-button-danger-outline" type="button" disabled={discard.isPending} onClick={() => setPending({ kind: "discard" })}>{t`Discard draft…`}</button> : null}
        <button className="desk-button-primary" type="submit" disabled={create.isPending || !draft.statuses.length}>{create.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : saved ? t`Save and review` : t`Save draft`}</button>
      </div>
    </div>
  </form>
    <ConfirmDialog open={pending !== null} tone={pending?.kind === "discard" ? "danger" : "default"} pending={discard.isPending}
      title={pending?.kind === "discard" ? t`Discard this draft?` : t`Replace your draft?`}
      message={pending?.kind === "discard" ? t`Your subject, message, design and audience are removed and the composer starts empty. This cannot be undone.`
        : pending ? t`Loading the “${pending.template.label}” template replaces what you have written. Your saved draft is updated with the template.` : ""}
      confirmLabel={pending?.kind === "discard" ? t`Discard draft` : t`Replace draft`} cancelLabel={t`Keep my draft`}
      onCancel={() => setPending(null)} onConfirm={confirmPending} />
  </Card>;
}
